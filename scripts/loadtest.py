import asyncio
import aiohttp

async def hammer(session, key, n=200):
    allowed = rejected = 0
    for _ in range(n):
        async with session.post('http://localhost:8080/v1/check',
            json={"key": key, "algorithm": "sliding_window"}) as r:
            data = await r.json()
            if data["allowed"]: allowed += 1
            else: rejected += 1
    return allowed, rejected

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [hammer(session, f"user:{i}", 200) for i in range(20)]
        results = await asyncio.gather(*tasks)
        total_allowed = sum(r[0] for r in results)
        total_rejected = sum(r[1] for r in results)
        total = total_allowed + total_rejected
        print(f"Allowed:        {total_allowed}")
        print(f"Rejected:       {total_rejected}")
        print(f"Total:          {total}")
        print(f"Rejection rate: {total_rejected/total*100:.1f}%")

asyncio.run(main())