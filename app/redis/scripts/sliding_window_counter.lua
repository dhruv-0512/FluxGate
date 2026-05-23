local curr_key = KEYS[1]    -- current window key
local prev_key = KEYS[2]    -- previous window key
local limit = tonumber(ARGV[1])
local now_ms = tonumber(ARGV[2])
local window_ms = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

-- get counts
local curr_count = tonumber(redis.call('GET', curr_key)) or 0
local prev_count = tonumber(redis.call('GET', prev_key)) or 0

-- how far into current window are we (0.0 to 1.0)
local window_start = math.floor(now_ms / window_ms) * window_ms
local elapsed_ratio = (now_ms - window_start) / window_ms

-- weighted count: previous window contributes less as time passes
local weighted_count = math.floor(prev_count * (1 - elapsed_ratio) + curr_count)

if weighted_count + requested <= limit then
    -- increment current window
    local new_count = redis.call('INCRBY', curr_key, requested)
    redis.call('PEXPIRE', curr_key, window_ms * 2)  -- keep for 2 windows
    return {1, limit - weighted_count - requested, 0}
else
    -- calculate retry after
    local retry_after = math.ceil(window_ms - (now_ms - window_start))
    return {0, 0, retry_after}
end