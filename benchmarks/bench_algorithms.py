"""
Benchmark each algorithm individually.
Measures p50, p95, p99 latency per algorithm.
"""
import asyncio
import aiohttp
import time
import statistics

BASE_URL = "http://localhost:8080"
ALGORITHMS = ["token_bucket", "sliding_window", "sliding_window_counter", "leaky_bucket"]
REQUESTS_PER_ALGO = 500


async def bench_algorithm(session, algorithm: str):
    latencies = []
    allowed = rejected = errors = 0

    for i in range(REQUESTS_PER_ALGO):
        start = time.perf_counter()
        async with session.post(f"{BASE_URL}/v1/check", json={
            "key": f"bench:{algorithm}:{i % 10}",
            "algorithm": algorithm,
            "n": 1
        }) as r:
            elapsed = (time.perf_counter() - start) * 1000
            if r.status != 200:
                text = await r.text()
                print(f"\n  ERROR {r.status} [{algorithm}] req {i}: {text[:200]}")
                errors += 1
                continue
            data = await r.json(content_type=None)
            latencies.append(elapsed)
            if data["allowed"]:
                allowed += 1
            else:
                rejected += 1

    if not latencies:
        return {
            "algorithm": algorithm,
            "requests": REQUESTS_PER_ALGO,
            "allowed": 0, "rejected": 0, "errors": errors,
            "p50_ms": 0, "p95_ms": 0, "p99_ms": 0,
            "min_ms": 0, "max_ms": 0,
        }

    latencies.sort()
    return {
        "algorithm": algorithm,
        "requests": REQUESTS_PER_ALGO,
        "allowed": allowed,
        "rejected": rejected,
        "errors": errors,
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
        "p99_ms": round(latencies[int(len(latencies) * 0.99)], 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
    }


async def main():
    print(f"\n{'─'*65}")
    print(f"  FluxGate Algorithm Benchmark — {REQUESTS_PER_ALGO} req per algorithm")
    print(f"{'─'*65}")
    print(f"  {'Algorithm':<28} {'p50':>6} {'p95':>6} {'p99':>6} {'min':>6} {'max':>6}")
    print(f"{'─'*65}")

    async with aiohttp.ClientSession() as session:
        # reset all keys first
        for algo in ALGORITHMS:
            for i in range(10):
                await session.post(f"{BASE_URL}/v1/reset/bench:{algo}:{i}")

        for algo in ALGORITHMS:
            result = await bench_algorithm(session, algo)
            if result["errors"] > 0:
                print(f"  {result['algorithm']:<28}  {result['errors']} errors — check backend logs")
            else:
                print(
                    f"  {result['algorithm']:<28}"
                    f"  {result['p50_ms']:>5}ms"
                    f"  {result['p95_ms']:>5}ms"
                    f"  {result['p99_ms']:>5}ms"
                    f"  {result['min_ms']:>5}ms"
                    f"  {result['max_ms']:>5}ms"
                )

    print(f"{'─'*65}\n")


asyncio.run(main())