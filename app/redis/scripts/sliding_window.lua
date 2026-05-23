local key = KEYS[1]
local window_ms = tonumber(ARGV[1])    -- window size in ms
local limit = tonumber(ARGV[2])        -- max requests allowed
local now = tonumber(ARGV[3])          -- current time in ms
local requested = tonumber(ARGV[4])

-- remove all entries outside the window
redis.call('ZREMRANGEBYSCORE', key, 0, now - window_ms)

-- count current requests in window
local count = tonumber(redis.call('ZCARD', key))

if count + requested <= limit then
    -- add requested number of entries
    for i = 1, requested do
        redis.call('ZADD', key, now, now .. ':' .. i .. ':' .. math.random(100000))
    end
    redis.call('PEXPIRE', key, window_ms)
    return {1, limit - count - requested, 0}
else
    -- get oldest entry to calculate retry_after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 0
    if #oldest > 0 then
        retry_after = math.ceil(tonumber(oldest[2]) + window_ms - now)
    end
    return {0, 0, retry_after}
end