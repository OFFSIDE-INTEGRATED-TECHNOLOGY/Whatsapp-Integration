from .token_bucket import RedisTokenBucketLimiter

# Re-export alias for clarity in other imports
RATE_LIMITER = RedisTokenBucketLimiter()
__all__ = ["RedisTokenBucketLimiter", "RATE_LIMITER"]
