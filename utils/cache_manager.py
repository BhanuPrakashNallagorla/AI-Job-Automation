"""
Cache Manager for Redis-based caching.
Fallback to in-memory cache if Redis unavailable.
"""
import json
import hashlib
from datetime import date
from typing import Optional, Any
import structlog

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


logger = structlog.get_logger(__name__)


class CacheManager:
    """
    Cache manager with Redis backend.
    Falls back to in-memory cache if Redis unavailable.
    """
    
    def __init__(self, redis_url: Optional[str] = None, ttl: int = 604800):
        """
        Initialize cache manager.
        
        Args:
            redis_url: Redis connection URL (optional)
            ttl: Cache TTL in seconds (default: 7 days)
        """
        self.ttl = ttl
        self.redis_client = None
        self._memory_cache: dict = {}
        self._usage_counter: dict = {}
        
        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis unavailable, using memory cache: {e}")
                self.redis_client = None
    
    def _generate_key(self, operation: str, data: str) -> str:
        """Generate cache key from operation and data."""
        hash_value = hashlib.md5(data.encode()).hexdigest()
        return f"autoapply:{operation}:{hash_value}"
    
    def get(self, operation: str, data: str) -> Optional[Any]:
        """Get cached result."""
        key = self._generate_key(operation, data)
        
        if self.redis_client:
            try:
                cached = self.redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        
        # Fallback to memory
        return self._memory_cache.get(key)
    
    def set(self, operation: str, data: str, result: Any) -> None:
        """Cache result."""
        key = self._generate_key(operation, data)
        
        if self.redis_client:
            try:
                self.redis_client.setex(key, self.ttl, json.dumps(result))
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
        
        # Fallback to memory
        self._memory_cache[key] = result
    
    def get_daily_usage(self) -> int:
        """Get today's API usage count."""
        today = date.today().isoformat()
        key = f"usage:{today}"
        
        if self.redis_client:
            try:
                count = self.redis_client.get(key)
                return int(count) if count else 0
            except Exception:
                pass
        
        return self._usage_counter.get(today, 0)
    
    def increment_usage(self) -> int:
        """Increment daily usage counter."""
        today = date.today().isoformat()
        key = f"usage:{today}"
        
        if self.redis_client:
            try:
                self.redis_client.incr(key)
                self.redis_client.expire(key, 86400)
                return self.get_daily_usage()
            except Exception:
                pass
        
        self._usage_counter[today] = self._usage_counter.get(today, 0) + 1
        return self._usage_counter[today]
    
    def clear_cache(self, operation: Optional[str] = None) -> int:
        """Clear cache entries."""
        cleared = 0
        
        if self.redis_client:
            try:
                pattern = f"autoapply:{operation}:*" if operation else "autoapply:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    cleared = self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
        
        # Clear memory cache
        if operation:
            keys_to_delete = [k for k in self._memory_cache if operation in k]
            for k in keys_to_delete:
                del self._memory_cache[k]
            cleared += len(keys_to_delete)
        else:
            cleared += len(self._memory_cache)
            self._memory_cache.clear()
        
        return cleared
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        stats = {
            "backend": "redis" if self.redis_client else "memory",
            "daily_usage": self.get_daily_usage(),
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info("memory")
                stats["memory_used"] = info.get("used_memory_human", "unknown")
            except Exception:
                pass
        else:
            stats["memory_entries"] = len(self._memory_cache)
        
        return stats


# Singleton instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_url: Optional[str] = None) -> CacheManager:
    """Get or create cache manager."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(redis_url=redis_url)
    return _cache_manager
