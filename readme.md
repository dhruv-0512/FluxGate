````markdown
# FluxGate

A distributed rate limiting service built with FastAPI and Redis. Supports four algorithms with atomic Redis Lua scripts, a real-time WebSocket dashboard, Postgres audit logging, and hot config reload no restart required.

Built as a systems engineering project to demonstrate distributed backend design, concurrency, and infrastructure engineering.

---

## Demo

![Dashboard](./docs/dashboard.png)

> 20 concurrent clients, 4000 total requests, per-key enforcement enforcing exactly 100 req/window per user.

---

## Features

- **4 rate limiting algorithms** — token bucket, sliding window log, sliding window counter, leaky bucket
- **Redis Lua scripts** — atomic check-and-update, zero race conditions
- **Per-key limits** — enforce by user ID, IP, route, or any arbitrary key
- **Hot config reload** — edit `config.yaml`, changes apply instantly with no restart
- **Real-time dashboard** — WebSocket feed, live RPS, acceptance rate gauge, top throttled keys table
- **Postgres analytics** — every request logged, per-key history, global stats
- **Load tested** — 4000+ requests across 20 concurrent clients

---

## Algorithms

### Token Bucket
Fixed capacity bucket per key. Tokens refill at a constant rate. Allows controlled bursts up to capacity. Best for APIs that need to tolerate short traffic spikes.

### Sliding Window Log
Stores exact request timestamps in a Redis sorted set. Prunes entries outside the window on every request. Exact enforcement — no edge case double-spending. Best for strict per-second limits.

### Sliding Window Counter
Weighted approximation using two adjacent fixed windows. Memory efficient compared to the log variant. Formula: `count = prev_count × (1 - elapsed_ratio) + curr_count`. Best for high throughput APIs.

### Leaky Bucket
Requests enter a queue and drain at a fixed rate. Smooths bursty traffic into a steady stream. Best for protecting downstream services from sudden load spikes.

All four algorithms use **Redis Lua scripts** for atomic read-modify-write. This eliminates the race condition that exists when check and update are separate network calls.

---

## Architecture

```
Client → FastAPI → Rate Limiter → Redis (Lua atomic ops)
                        ↓
                   PostgreSQL (audit log)
                        ↓
                 React Dashboard (WebSocket)
```

```
fluxgate/
├── app/
│   ├── limiter/          # 4 algorithm implementations
│   ├── redis/            # client + Lua scripts
│   ├── api/              # HTTP routes + WebSocket
│   ├── config/           # config loader + hot reload watcher
│   ├── analytics/        # Postgres models + queries
│   ├── metrics/          # in-memory rolling window collector
│   └── main.py           # FastAPI app + lifespan
├── dashboard/            # React + Vite + Recharts
├── scripts/
│   └── loadtest.py
└── config.yaml
```

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, uvicorn |
| Rate limiting | Redis 7, Lua scripts |
| Analytics | PostgreSQL 15, asyncpg |
| Config reload | Watchdog (fsnotify equivalent) |
| Dashboard | React, Vite, Recharts, Lucide |
| Containerization | Docker |

---

## Quick Start

**Prerequisites:** Docker, Python 3.11+, Node 18+

```bash
# 0. create local config and env files
copy config.example.yaml config.yaml
copy .env.example .env

# 1. start redis and postgres
docker run -d -p 6379:6379 redis:7-alpine
docker run -d -e POSTGRES_DB=fluxgate -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=change_me -p 5432:5432 postgres:15

# 2. install python deps
pip install -r requirements.txt

# 3. start backend
python -m app.main

# 4. start dashboard (separate terminal)
cd dashboard
npm install
npm run dev
```

Open `http://localhost:5173`

Local secrets should live in `config.yaml` and `.env`, which are ignored by git.

---

## API Reference

### Check rate limit
```
POST /v1/check
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
POST /v1/check              check rate limit for a key
GET  /v1/status/{key}       current bucket state (non-consuming)
POST /v1/reset/{key}        reset a key's state
GET  /v1/metrics            global snapshot
GET  /v1/metrics/{key}      per-key request history
GET  /v1/rules              active config rules
POST /v1/config/reload      hot reload config.yaml
GET  /health                health check
WS   /ws/metrics            live metrics stream (1s interval)
```

### Response headers
Every response includes standard rate limit headers:
```
X-RateLimit-Remaining: 43
X-RateLimit-Reset: 1716000000
Retry-After: 3  (only on 429)
```

---

## Configuration

Create `config.yaml` from `config.example.yaml`, then edit it to define rules. Rules are matched by key pattern (glob syntax). Changes apply **instantly** without restarting the server.

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

## Load Testing

```bash
python scripts/loadtest.py
```

Fires 4000 requests across 20 concurrent clients (`user:0` through `user:19`), 200 requests per client. At default limits (100 req/60s per key), produces ~50% rejection rate.

Expected output:
```
Allowed:        2000
Rejected:       2000
Total:          4000
Rejection rate: 50.0%
```

---

## Key Design Decisions

**Why Lua scripts?**
Without atomicity, two concurrent requests can both read `tokens_available = 1`, both pass the check, and both decrement — allowing double the intended limit. Lua scripts execute as a single atomic operation on the Redis server, eliminating this race condition without locks.

**Why four algorithms?**
Each solves a different problem. Token bucket for burst tolerance. Sliding window log for exactness. Sliding window counter for memory efficiency at scale. Leaky bucket for downstream protection. A real service needs to pick the right tool per route.

**Why hot reload?**
Rate limit rules change frequently in production — during incidents, attacks, or scaling events. Requiring a restart to change a limit is unacceptable. Watchdog monitors `config.yaml` and swaps the config atomically on change.

---
## Benchmarks

See [`benchmarks/`](./benchmarks) for full methodology and scripts.

### Algorithm Latency (500 req each, local Redis)

| Algorithm | p50 | p95 | p99 | min |
|---|---|---|---|---|
| token_bucket | 11.49ms | 24.19ms | 52.29ms | 8.09ms |
| sliding_window | 12.27ms | 24.56ms | 83.41ms | 8.25ms |
| sliding_window_counter | 14.84ms | 28.84ms | 62.21ms | 9.03ms |
| leaky_bucket | 13.83ms | 34.49ms | 50.14ms | 9.12ms |

### Throughput (concurrent clients, sliding_window)

| Clients | Requests | Throughput | Rejection Rate |
|---|---|---|---|
| 5 | 500 | 416 req/sec | 0% |
| 20 | 4000 | 442 req/sec | 62.5% |
| 50 | 5000 | 546 req/sec | 40% |

---

## License

MIT
````