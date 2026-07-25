# FluxGate

A distributed rate limiting service with four algorithms, atomic Redis Lua enforcement, hot config reload, and a real-time WebSocket dashboard.

---

## Workflow

```
Client
  |
  v
FastAPI (/v1/check)
  |
  v
RATE LIMITER
  Match key against config.yaml rules (glob pattern)
  Select algorithm: token_bucket | sliding_window |
                    sliding_window_counter | leaky_bucket
  |
  v
REDIS (Lua script, atomic check-and-update)
  Single round trip, no race condition, no distributed lock
  |
  +-------------------------+
  |                         |
  v                         v
ALLOWED / REJECTED    PostgreSQL audit log
  Response headers      per-key + global request history
  X-RateLimit-*
  |                         |
  +-------------------------+
              |
              v
   WebSocket /ws/metrics (1s interval)
              |
              v
   React Dashboard
   live RPS, acceptance rate, top throttled keys

config.yaml  ---(Watchdog, hot reload)--->  RATE LIMITER
   (no restart required, rules swap atomically on save)
```

---

## Project Structure

```
fluxgate/
├── app/
│   ├── limiter/          4 algorithm implementations
│   ├── redis/            client + Lua scripts
│   ├── api/               HTTP routes + WebSocket
│   ├── config/            config loader + hot reload watcher
│   ├── analytics/         PostgreSQL models + queries
│   ├── metrics/           in-memory rolling window collector
│   └── main.py
├── dashboard/             React + Vite + Recharts
├── scripts/
│   └── loadtest.py
└── config.yaml
```

---

## Why FluxGate

Most rate limiters bolt on a single algorithm and call it done. FluxGate ships four, because token bucket, sliding window, and leaky bucket solve fundamentally different problems, and a real production service shouldn't be forced to pick one globally. Every algorithm runs through Redis Lua scripts for atomic check-and-update, eliminating the race condition that plagues naive implementations.

---

## Features

- Four algorithms: token bucket, sliding window log, sliding window counter, leaky bucket
- Atomic Redis Lua scripts: single-operation check-and-update, zero race conditions under concurrency
- Per-key enforcement: scope limits by user ID, IP, route, or any arbitrary key
- Hot config reload: edit `config.yaml`, changes apply instantly with no restart required
- Live WebSocket dashboard: real-time RPS, acceptance rate gauge, top throttled keys
- PostgreSQL audit log: every request recorded, per-key history and global stats queryable
- Load tested: 4,000+ requests across 20 concurrent clients at 442 req/sec

---

## Algorithms

### Token Bucket

Fixed-capacity bucket per key. Tokens refill at a constant rate, allowing controlled bursts up to capacity. Best for APIs that need to tolerate short traffic spikes without hard-dropping requests.

### Sliding Window Log

Stores exact request timestamps in a Redis sorted set, pruning entries outside the window on each request. Exact enforcement with no edge-case double-spending. Best for strict per-second limits.

### Sliding Window Counter

Weighted approximation using two adjacent fixed windows:

```
count = prev_count * (1 - elapsed_ratio) + curr_count
```

where `elapsed_ratio` is the fraction of the current window that has elapsed (time since window start divided by window duration). Memory-efficient compared to the log variant. Best for high-throughput APIs where approximate enforcement is acceptable.

### Leaky Bucket

Requests enter a queue and drain at a fixed rate, smoothing bursty traffic into a steady stream. Best for protecting downstream services from sudden load spikes.

All four algorithms use Redis Lua scripts for atomic read-modify-write. Without this, two concurrent requests can both read `tokens_available = 1`, both pass the check, and both decrement, silently doubling the allowed limit. Lua scripts execute as a single atomic operation on the Redis server, with no locks needed.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, uvicorn |
| Rate limiting | Redis 7, Lua scripts |
| Analytics | PostgreSQL 15, asyncpg |
| Config reload | Watchdog |
| Dashboard | React, Vite, Recharts, Lucide |
| Containerization | Docker |

---

## Quick Start

Prerequisites: Docker, Python 3.11+, Node 18+

```bash
# 1. Copy config and env files
cp config.example.yaml config.yaml
cp .env.example .env

# 2. Start Redis and PostgreSQL
docker run -d -p 6379:6379 redis:7-alpine
docker run -d \
  -e POSTGRES_DB=fluxgate \
  -e POSTGRES_USER=admin \
  -e POSTGRES_PASSWORD=change_me \
  -p 5432:5432 postgres:15

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Start the backend
python -m app.main

# 5. Start the dashboard (separate terminal)
cd dashboard && npm install && npm run dev
```

Open `http://localhost:5173`

Local secrets live in `config.yaml` and `.env`, both gitignored.

---

## Configuration

Rules are matched by key pattern (glob syntax). Changes to `config.yaml` apply instantly without restarting.

```yaml
server:
  host: "0.0.0.0"
  port: 8080

redis:
  url: "redis://localhost:6379"

postgres:
  url: "postgresql+asyncpg://user:password@localhost/fluxgate"

rules:
  - name: "login_endpoint"
    key_pattern: "route:/api/login:*"
    algorithm: token_bucket
    capacity: 5
    refill_rate: 0.1          # 1 token per 10 seconds

  - name: "premium_users"
    key_pattern: "user:premium:*"
    algorithm: sliding_window
    limit: 1000
    window_seconds: 60

  - name: "default_api"
    key_pattern: "api:*"
    algorithm: sliding_window
    limit: 100
    window_seconds: 60

  - name: "ip_global"
    key_pattern: "ip:*"
    algorithm: leaky_bucket
    rate: 50
    burst: 10
```

---

## API Reference

### Check rate limit

```
POST /v1/check
```

```json
{
  "key": "user:123",
  "algorithm": "sliding_window",
  "n": 1
}
```

Response:

```json
{
  "allowed": true,
  "remaining": 43,
  "reset_after_ms": 60000,
  "retry_after_ms": 0,
  "key": "user:123",
  "algorithm": "sliding_window"
}
```

### All endpoints

```
POST /v1/check              Check rate limit for a key
GET  /v1/status/{key}       Current bucket state (non-consuming)
POST /v1/reset/{key}        Reset a key's state
GET  /v1/metrics            Global snapshot
GET  /v1/metrics/{key}      Per-key request history
GET  /v1/rules              Active config rules
POST /v1/config/reload      Hot reload config.yaml
GET  /health                Health check
WS   /ws/metrics            Live metrics stream (1s interval)
```

### Response headers

Every response includes standard rate limit headers:

```
X-RateLimit-Remaining: 43
X-RateLimit-Reset: 1716000000
Retry-After: 3              # only on 429
```

---

## Load Testing

```bash
python scripts/loadtest.py
```

Fires 4,000 requests across 20 concurrent clients (`user:0` through `user:19`), 200 requests per client. At the default limit of 100 req/60s per key, this produces roughly 50% rejection.

```
Allowed:        2000
Rejected:       2000
Total:          4000
Rejection rate: 50.0%
```

---

## Benchmarks

### Algorithm latency (500 requests each, local Redis)

| Algorithm | p50 | p95 | p99 | min |
|---|---|---|---|---|
| token_bucket | 11.49ms | 24.19ms | 52.29ms | 8.09ms |
| sliding_window | 12.27ms | 24.56ms | 83.41ms | 8.25ms |
| sliding_window_counter | 14.84ms | 28.84ms | 62.21ms | 9.03ms |
| leaky_bucket | 13.83ms | 34.49ms | 50.14ms | 9.12ms |

### Throughput (sliding_window)

| Clients | Requests | Throughput | Rejection Rate |
|---|---|---|---|
| 5 | 500 | 416 req/sec | 0% |
| 20 | 4,000 | 442 req/sec | 62.5% |
| 50 | 5,000 | 546 req/sec | 40% |

---

## Design Decisions

Why Lua scripts: without atomicity, two concurrent requests can both read `tokens_available = 1`, both pass, and both decrement, silently exceeding the limit. Lua scripts run as a single atomic unit on the Redis server, with no distributed locks required.

Why four algorithms: each solves a distinct problem. Token bucket for burst tolerance, sliding window log for exactness, sliding window counter for memory efficiency at scale, leaky bucket for downstream protection. One algorithm globally is the wrong abstraction.

Why hot reload: rate limit rules change during incidents, attacks, and scaling events. Requiring a restart to update a limit is a production liability. Watchdog monitors `config.yaml` and swaps the config atomically on save.

---

## License

MIT
