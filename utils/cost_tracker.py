"""
Cost Tracker for LLM API usage.
Tracks token usage and costs with budget alerts.
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import structlog

from config import settings


logger = structlog.get_logger(__name__)


# Pricing per 1K tokens (as of 2024)
MODEL_PRICING = {
    "claude-opus-4-20250514": {
        "input": 0.015,   # $15 per 1M input tokens
        "output": 0.075,  # $75 per 1M output tokens
    },
    "claude-sonnet-4-20250514": {
        "input": 0.003,   # $3 per 1M input tokens
        "output": 0.015,  # $15 per 1M output tokens
    },
    "claude-3-haiku-20240307": {
        "input": 0.00025,
        "output": 0.00125,
    },
}

# Default pricing for unknown models
DEFAULT_PRICING = {
    "input": 0.01,
    "output": 0.03,
}


class CostTracker:
    """
    Tracks LLM API costs with budget alerts.
    
    Features:
    - Per-operation cost tracking
    - Daily/monthly summaries
    - Budget alerts
    - Cost optimization suggestions
    """
    
    def __init__(self, costs_file: Optional[str] = None):
        """Initialize cost tracker."""
        self.costs_file = Path(costs_file or "data/costs.json")
        self.costs_file.parent.mkdir(parents=True, exist_ok=True)
        self._costs: List[Dict[str, Any]] = []
        self._load_costs()
        self.logger = logger.bind(component="CostTracker")
    
    def _load_costs(self) -> None:
        """Load costs from file."""
        if self.costs_file.exists():
            try:
                with open(self.costs_file, "r") as f:
                    self._costs = json.load(f)
            except Exception as e:
                self.logger.warning("Failed to load costs file", error=str(e))
                self._costs = []
    
    def _save_costs(self) -> None:
        """Save costs to file."""
        try:
            with open(self.costs_file, "w") as f:
                json.dump(self._costs, f, indent=2)
        except Exception as e:
            self.logger.warning("Failed to save costs file", error=str(e))
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calculate cost for an API call.
        
        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    def track_api_call(
        self,
        operation_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        job_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Track an API call and its cost.
        
        Args:
            operation_type: Type of operation (jd_analysis, resume_tailor, etc.)
            model: Model used
            input_tokens: Input token count
            output_tokens: Output token count
            job_id: Optional job ID reference
            description: Optional description
            
        Returns:
            Cost entry dict
        """
        cost_usd = self.calculate_cost(model, input_tokens, output_tokens)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation_type": operation_type,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "job_id": job_id,
            "description": description,
        }
        
        self._costs.append(entry)
        self._save_costs()
        
        self.logger.info(
            "API call tracked",
            operation=operation_type,
            cost=cost_usd,
            tokens=input_tokens + output_tokens
        )
        
        # Check budget alert
        self._check_budget_alert()
        
        return entry
    
    def _check_budget_alert(self) -> None:
        """Check if daily budget is exceeded and log warning."""
        today_cost = self.get_today_cost()
        
        if today_cost >= settings.daily_budget_usd:
            self.logger.warning(
                "Daily budget exceeded!",
                today_cost=today_cost,
                budget=settings.daily_budget_usd
            )
        elif today_cost >= settings.daily_budget_usd * 0.8:
            self.logger.warning(
                "Approaching daily budget limit",
                today_cost=today_cost,
                budget=settings.daily_budget_usd,
                remaining=settings.daily_budget_usd - today_cost
            )
    
    def get_today_cost(self) -> float:
        """Get total cost for today."""
        today = datetime.now().date()
        
        total = 0.0
        for entry in self._costs:
            entry_date = datetime.fromisoformat(entry["timestamp"]).date()
            if entry_date == today:
                total += entry.get("cost_usd", 0)
        
        return round(total, 4)
    
    def get_cost_summary(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get cost summary for a time period.
        
        Args:
            days: Number of days to include
            
        Returns:
            Cost summary dict
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        filtered = [
            entry for entry in self._costs
            if datetime.fromisoformat(entry["timestamp"]) >= cutoff
        ]
        
        # Aggregate by operation type
        by_operation: Dict[str, Dict[str, Any]] = {}
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        
        for entry in filtered:
            op_type = entry.get("operation_type", "unknown")
            
            if op_type not in by_operation:
                by_operation[op_type] = {
                    "cost_usd": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "calls": 0,
                }
            
            by_operation[op_type]["cost_usd"] += entry.get("cost_usd", 0)
            by_operation[op_type]["input_tokens"] += entry.get("input_tokens", 0)
            by_operation[op_type]["output_tokens"] += entry.get("output_tokens", 0)
            by_operation[op_type]["calls"] += 1
            
            total_cost += entry.get("cost_usd", 0)
            total_input_tokens += entry.get("input_tokens", 0)
            total_output_tokens += entry.get("output_tokens", 0)
        
        # Aggregate by day
        by_day: Dict[str, float] = {}
        for entry in filtered:
            day = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0) + entry.get("cost_usd", 0)
        
        daily_costs = [
            {"date": date, "cost_usd": round(cost, 4)}
            for date, cost in sorted(by_day.items())
        ]
        
        return {
            "period_days": days,
            "total_cost_usd": round(total_cost, 4),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_calls": len(filtered),
            "avg_cost_per_call": round(total_cost / len(filtered), 4) if filtered else 0,
            "by_operation": {
                k: {
                    **v,
                    "cost_usd": round(v["cost_usd"], 4),
                }
                for k, v in by_operation.items()
            },
            "daily_costs": daily_costs,
            "budget_status": {
                "daily_budget": settings.daily_budget_usd,
                "today_spent": self.get_today_cost(),
                "remaining_today": max(0, settings.daily_budget_usd - self.get_today_cost()),
            }
        }
    
    def get_optimization_suggestions(self) -> List[str]:
        """Get suggestions to optimize costs."""
        suggestions = []
        summary = self.get_cost_summary(days=7)
        
        by_operation = summary.get("by_operation", {})
        
        # Check for expensive operations
        if by_operation.get("resume_tailor", {}).get("calls", 0) > 10:
            suggestions.append(
                "Consider batching resume tailoring operations to reduce API calls"
            )
        
        # Check model usage
        opus_cost = 0
        sonnet_cost = 0
        for cost in self._costs[-50:]:  # Last 50 entries
            if "opus" in cost.get("model", "").lower():
                opus_cost += cost.get("cost_usd", 0)
            else:
                sonnet_cost += cost.get("cost_usd", 0)
        
        if opus_cost > sonnet_cost * 2:
            suggestions.append(
                "Consider using Claude Sonnet instead of Opus for routine operations"
            )
        
        # Check cache usage
        jd_analysis = by_operation.get("jd_analysis", {})
        if jd_analysis.get("calls", 0) > 20:
            suggestions.append(
                "Ensure JD analysis caching is enabled to avoid re-analyzing same descriptions"
            )
        
        if not suggestions:
            suggestions.append("No optimization suggestions - usage looks efficient!")
        
        return suggestions


# Module-level instance for convenience
_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get or create the global cost tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker


def track_api_call(
    operation_type: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to track an API call."""
    return get_tracker().track_api_call(
        operation_type=operation_type,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        **kwargs
    )


def get_cost_report(days: int = 30) -> Dict[str, Any]:
    """Convenience function to get cost report."""
    return get_tracker().get_cost_summary(days=days)
