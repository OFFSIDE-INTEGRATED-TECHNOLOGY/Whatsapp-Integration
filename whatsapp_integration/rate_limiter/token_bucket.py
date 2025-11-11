import time
import redis
from django.conf import settings

class RedisTokenBucketLimiter:
    """Implements Lua-based Redis token bucket rate limiter."""

    def __init__(self, redis_url=None):
        self.redis = redis.from_url(redis_url or settings.REDIS_URL)
        with open(settings.BASE_DIR / "whatsapp_integration/rate_limiter/lua_token_bucket.lua", "r") as f:
            self.lua_script = f.read()
        self.sha = self.redis.script_load(self.lua_script)

    def allow(self, key="whatsapp:webhook", max_tokens=10, rate_per_sec=1.5) -> bool:
        now = int(time.time())
        try:
            result = self.redis.evalsha(self.sha, 1, key, max_tokens, rate_per_sec, now)
            return result == 1
        except redis.exceptions.ResponseError:
            # Fallback if script cache is flushed
            result = self.redis.eval(self.lua_script, 1, key, max_tokens, rate_per_sec, now)
            return result == 1
