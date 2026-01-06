"""
Cost Tracker for LLM API usage.
Updated for Gemini (FREE tier) - tracks usage without costs.
"""
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import structlog

from config import settings


logger = structlog.get_logger(__name__)


class CostTracker:
    """
    Tracks API usage for analytics.
    Gemini is FREE, but we still track for monitoring.
    """
    
    def __init__(self, costs_file: Optional[str] = None):
        """Initialize cost tracker."""
        self.costs_file = Path(costs_file or "data/usage.json")
        self.costs_file.parent.mkdir(parents=True, exist_ok=True)
        self._entries: List[Dict[str, Any]] = []
        self._load()
        self.logger = logger.bind(component="CostTracker")
    
    def _load(self) -> None:
        """Load usage history from file."""
        if self.costs_file.exists():
            try:
                with open(self.costs_file, "r") as f:
                    self._entries = json.load(f)
            except Exception as e:
                self.logger.warning("Failed to load usage file", error=str(e))
                self._entries = []
    
    def _save(self) -> None:
        """Save usage history to file."""
        try:
            with open(self.costs_file, "w") as f:
                json.dump(self._entries, f, indent=2)
        except Exception as e:
            self.logger.warning("Failed to save usage file", error=str(e))
    
    def track_api_call(
        self,
        operation_type: str,
        model: str = "gemini-2.0-flash-exp",
        input_chars: int = 0,
        output_chars: int = 0,
        job_id: Optional[str] = None,
        description: Optional[str] = None,
        cached: bool = False,
    ) -> Dict[str, Any]:
        """
        Track an API call for analytics.
        
        Gemini is FREE, so cost is always $0.00
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation_type": operation_type,
            "model": model,
            "input_chars": input_chars,
            "output_chars": output_chars,
            "cost_usd": 0.00,  # FREE!
            "job_id": job_id,
            "description": description,
            "cached": cached,
        }
        
        self._entries.append(entry)
        self._save()
        
        self.logger.info(
            "API call tracked",
            operation=operation_type,
            cached=cached
        )
        
        return entry
    
    def get_today_usage(self) -> int:
        """Get total requests for today."""
        today = datetime.now().date()
        
        count = 0
        for entry in self._entries:
            entry_date = datetime.fromisoformat(entry["timestamp"]).date()
            if entry_date == today:
                count += 1
        
        return count
    
    def get_usage_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get usage summary for a time period."""
        cutoff = datetime.now() - timedelta(days=days)
        
        filtered = [
            entry for entry in self._entries
            if datetime.fromisoformat(entry["timestamp"]) >= cutoff
        ]
        
        # Aggregate by operation type
        by_operation: Dict[str, int] = {}
        cached_count = 0
        
        for entry in filtered:
            op_type = entry.get("operation_type", "unknown")
            by_operation[op_type] = by_operation.get(op_type, 0) + 1
            if entry.get("cached"):
                cached_count += 1
        
        # Daily breakdown
        by_day: Dict[str, int] = {}
        for entry in filtered:
            day = datetime.fromisoformat(entry["timestamp"]).strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0) + 1
        
        total = len(filtered)
        cache_hit_rate = (cached_count / total * 100) if total > 0 else 0
        
        return {
            "period_days": days,
            "total_requests": total,
            "cached_requests": cached_count,
            "cache_hit_rate": round(cache_hit_rate, 1),
            "by_operation": by_operation,
            "daily_usage": [
                {"date": date, "requests": count}
                for date, count in sorted(by_day.items())
            ],
            "cost_usd": 0.00,  # FREE!
            "savings_vs_openai": round(total * 0.015, 2),  # Estimated savings
        }


# Module-level instance
_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get or create the global cost tracker."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker


def track_api_call(
    operation_type: str,
    model: str = "gemini-2.0-flash-exp",
    input_chars: int = 0,
    output_chars: int = 0,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function to track an API call."""
    return get_tracker().track_api_call(
        operation_type=operation_type,
        model=model,
        input_chars=input_chars,
        output_chars=output_chars,
        **kwargs
    )


def get_cost_report(days: int = 30) -> Dict[str, Any]:
    """Convenience function to get usage report."""
    return get_tracker().get_usage_summary(days=days)
