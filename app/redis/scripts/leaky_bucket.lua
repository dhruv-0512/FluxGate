local key = KEYS[1]
local rate = tonumber(ARGV[1])        -- requests per second to leak
local burst = tonumber(ARGV[2])       -- max queue size
local now = tonumber(ARGV[3])         -- current time in ms
local requested = tonumber(ARGV[4])

-- get current state
local bucket = redis.call('HMGET', key, 'queue', 'last_leak')
local queue = tonumber(bucket[1]) or 0
local last_leak = tonumber(bucket[2]) or now

-- leak: remove processed requests based on elapsed time
local elapsed = (now - last_leak) / 1000   -- ms to seconds
local leaked = math.floor(elapsed * rate)

if leaked > 0 then
    queue = math.max(0, queue - leaked)
    last_leak = now
end

-- check if request fits in queue
if queue + requested <= burst then
    queue = queue + requested
    redis.call('HMSET', key, 'queue', queue, 'last_leak', last_leak)
    redis.call('EXPIRE', key, 3600)
    local remaining = burst - queue
    return {1, remaining, 0}
else
    redis.call('HMSET', key, 'queue', queue, 'last_leak', last_leak)
    redis.call('EXPIRE', key, 3600)
    -- retry after queue drains enough
    local overflow = queue + requested - burst
    local retry_after = math.ceil((overflow / rate) * 1000)
    return {0, 0, retry_after}
end