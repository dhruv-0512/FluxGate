local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])   -- tokens per second
local now = tonumber(ARGV[3])           -- current time in ms
local requested = tonumber(ARGV[4])

-- get current bucket state
local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

-- first request ever for this key
if tokens == nil then
    tokens = capacity
    last_refill = now
end

-- refill based on time elapsed
local elapsed = (now - last_refill) / 1000   -- convert ms to seconds
local new_tokens = math.min(capacity, tokens + elapsed * refill_rate)

-- check and consume
if new_tokens >= requested then
    redis.call('HMSET', key, 'tokens', new_tokens - requested, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    return {1, math.floor(new_tokens - requested), 0}
    -- {allowed, remaining, retry_after_ms}
else
    redis.call('HMSET', key, 'tokens', new_tokens, 'last_refill', now)
    redis.call('EXPIRE', key, 3600)
    local tokens_needed = requested - new_tokens
    local retry_after = math.ceil((tokens_needed / refill_rate) * 1000)
    return {0, math.floor(new_tokens), retry_after}
end