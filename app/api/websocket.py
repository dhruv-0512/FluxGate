import asyncio
import json
import logging
import time
from fastapi import WebSocket, WebSocketDisconnect
from app.metrics.collector import MetricsCollector

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict):
        if not self.active:
            return
        message = json.dumps(data)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def metrics_broadcaster(metrics: MetricsCollector):
    while True:
        try:
            if manager.active:
                snapshot = await metrics.get_snapshot()
                snapshot["type"] = "metrics"
                await manager.broadcast(snapshot)
        except Exception as e:
            logger.error(f"Broadcaster error: {e}")
        await asyncio.sleep(1)


async def ws_endpoint(websocket: WebSocket, metrics: MetricsCollector):
    await manager.connect(websocket)
    try:
        snapshot = await metrics.get_snapshot()
        snapshot["type"] = "metrics"
        await websocket.send_text(json.dumps(snapshot))
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat", "timestamp": time.time()}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WS error: {e}")
        manager.disconnect(websocket)