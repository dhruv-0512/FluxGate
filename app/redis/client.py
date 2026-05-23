import redis.asyncio as redis
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent / "scripts"


class RedisClient:
    def __init__(self, url: str = "redis://localhost:6379"):
        self.url = url
        self.client: redis.Redis = None
        self._scripts: dict[str, str] = {}   # script name → SHA

    async def connect(self):
        self.client = await redis.from_url(
            self.url,
            encoding="utf-8",
            decode_responses=True
        )
        await self.client.ping()
        await self._load_scripts()
        print("Redis connected")

    async def disconnect(self):
        if self.client:
            await self.client.aclose()

    async def _load_scripts(self):
        """Load all Lua scripts and cache their SHAs"""
        for script_path in SCRIPTS_DIR.glob("*.lua"):
            name = script_path.stem
            source = script_path.read_text()
            sha = await self.client.script_load(source)
            self._scripts[name] = sha
            print(f"Loaded script: {name} -> {sha[:8]}...")

    async def run_script(
        self,
        name: str,
        keys: list[str],
        args: list
    ):
        sha = self._scripts.get(name)
        if not sha:
            raise ValueError(f"Script '{name}' not loaded")
        return await self.client.evalsha(sha, len(keys), *keys, *args)

    async def ping(self) -> bool:
        try:
            return await self.client.ping()
        except Exception:
            return False