-- KEYS[1] = key
-- ARGV[1] = max tokens
-- ARGV[2] = refill rate per second
-- ARGV[3] = current timestamp in seconds

local key = KEYS[1]
local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local data = redis.call("HMGET", key, "tokens", "timestamp")
local tokens = tonumber(data[1])
local timestamp = tonumber(data[2])

if tokens == nil then
  tokens = max_tokens
  timestamp = now
end

local delta = math.max(0, now - timestamp)
local refill = delta * refill_rate
tokens = math.min(max_tokens, tokens + refill)
timestamp = now

local allowed = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
end

redis.call("HMSET", key, "tokens", tokens, "timestamp", timestamp)
redis.call("EXPIRE", key, 3600)

return allowed
