import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.config.config import load_config
from app.config.watcher import ConfigWatcher
from app.redis.client import RedisClient
from app.analytics.postgres import AnalyticsDB
from app.metrics.collector import MetricsCollector
from app.api.routes import router
from app.api.websocket import ws_endpoint, metrics_broadcaster

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FluxGate...")
    config = load_config()

    app.state.redis = RedisClient(url=config.redis.url)
    await app.state.redis.connect()

    app.state.db = AnalyticsDB(url=config.postgres.url)
    await app.state.db.connect()

    app.state.metrics = MetricsCollector(window_seconds=60)

    loop = asyncio.get_event_loop()
    app.state.watcher = ConfigWatcher("config.yaml")
    app.state.watcher.start(loop)

    app.state.broadcaster = asyncio.create_task(
        metrics_broadcaster(app.state.metrics)
    )

    logger.info(f"FluxGate running on :{config.server.port}")
    logger.info(f"Loaded {len(config.rules)} rules from config.yaml")

    yield

    logger.info("Shutting down...")
    app.state.broadcaster.cancel()
    app.state.watcher.stop()
    await app.state.redis.disconnect()
    await app.state.db.disconnect()
    logger.info("Shutdown complete")


app = FastAPI(title="FluxGate", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    await ws_endpoint(websocket, websocket.app.state.metrics)


if __name__ == "__main__":
    import uvicorn
    config = load_config()
    uvicorn.run("app.main:app", host=config.server.host, port=config.server.port, reload=False)