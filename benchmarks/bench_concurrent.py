"""
Concurrency stress test.
Fires N concurrent clients simultaneously, measures throughput and correctness.
"""
import asyncio
import aiohttp
import time
import statistics

BASE_URL = "http://localhost:8080"


async def client(session, client_id: int, requests: int, algorithm: str):
    latencies = []
    allowed = rejected = 0
    key = f"stress:{client_id}"

    for _ in range(requests):
        start = time.perf_counter()
        async with session.post(f"{BASE_URL}/v1/check", json={
            "key": key,
            "algorithm": algorithm,
            "n": 1
        }) as r:
            data = await r.json()
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            if data["allowed"]: allowed += 1
            else: rejected += 1

    return allowed, rejected, latencies


async def run_stress(clients: int, requests_per_client: int, algorithm: str):
    print(f"\n  {clients} clients × {requests_per_client} req — {algorithm}")
    print(f"  {'─'*50}")

    start = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        tasks = [
            client(session, i, requests_per_client, algorithm)
            for i in range(clients)
        ]
        results = await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - start

    total_allowed = sum(r[0] for r in results)
    total_rejected = sum(r[1] for r in results)
    total = total_allowed + total_rejected
    all_latencies = sorted([l for r in results for l in r[2]])
    rps = round(total / elapsed, 1)

    print(f"  Total requests : {total}")
    print(f"  Allowed        : {total_allowed}")
    print(f"  Rejected       : {total_rejected}")
    print(f"  Rejection rate : {total_rejected/total*100:.1f}%")
    print(f"  Duration       : {elapsed:.2f}s")
    print(f"  Throughput     : {rps} req/sec")
    print(f"  Latency p50    : {statistics.median(all_latencies):.2f}ms")
    print(f"  Latency p95    : {all_latencies[int(len(all_latencies)*0.95)]:.2f}ms")
    print(f"  Latency p99    : {all_latencies[int(len(all_latencies)*0.99)]:.2f}ms")


async def main():
    print(f"\n{'═'*55}")
    print(f"  FluxGate Concurrency Stress Test")
    print(f"{'═'*55}")

    # test 1: light load
    await run_stress(clients=5, requests_per_client=100, algorithm="sliding_window")

    # test 2: medium load
    await run_stress(clients=20, requests_per_client=200, algorithm="sliding_window")

    # test 3: heavy load
    await run_stress(clients=50, requests_per_client=100, algorithm="sliding_window")

    # test 4: token bucket under pressure
    await run_stress(clients=20, requests_per_client=100, algorithm="token_bucket")

    # test 5: leaky bucket
    await run_stress(clients=20, requests_per_client=100, algorithm="leaky_bucket")

    print(f"\n{'═'*55}\n")


asyncio.run(main())