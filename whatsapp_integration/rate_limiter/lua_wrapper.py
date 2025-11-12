# wrapper to load lua script and call atomically via EVALSHA
import redis
import os
import time
from django.conf import settings
REDIS_URL = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")

class LuaRateLimiter:
    def __init__(self, r, sha, capacity, rate, prefix="whatsapp"):
        self.r = r
        self.sha = sha
        self.capacity = capacity
        self.rate = rate
        self.prefix = prefix

    @classmethod
    def from_settings(cls, prefix="whatsapp", rate_key="WHATSAPP_RATE_PER_SECOND"):
        r = redis.Redis.from_url(REDIS_URL)
        # parameters
        rate = float(getattr(__import__("django.conf").conf.settings, rate_key, 1.0))
        capacity = max(1.0, rate * 60.0)
        # load script
        path = os.path.join(os.path.dirname(__file__), "lua_token_bucket.lua")
        with open(path, "r") as fh:
            script = fh.read()
        sha = r.script_load(script)
        return cls(r, sha, capacity, rate, prefix=prefix)

    def _key(self, k):
        return f"{self.prefix}:bucket:{k}"

    def consume(self, key, tokens=1.0):
        now = time.time()
        try:
            res = self.r.evalsha(self.sha, 1, self._key(key), self.capacity, self.rate, now, tokens)
            # returned [allowed, new_tokens]
            allowed = int(res[1-1])  # res[0]
            return bool(allowed)
        except redis.exceptions.NoScriptError:
            # reload
            with open(os.path.join(os.path.dirname(__file__), "lua_token_bucket.lua"), "r") as fh:
                script = fh.read()
            self.sha = self.r.script_load(script)
            res = self.r.evalsha(self.sha, 1, self._key(key), self.capacity, self.rate, now, tokens)
            allowed = int(res[1-1])
            return bool(allowed)
