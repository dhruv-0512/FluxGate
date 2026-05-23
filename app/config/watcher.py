import asyncio
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from app.config.config import load_config, get_config

logger = logging.getLogger(__name__)


class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config_path: str, loop: asyncio.AbstractEventLoop):
        self.config_path = Path(config_path).resolve()
        self.loop = loop
        self._reload_task = None

    def on_modified(self, event):
        if Path(event.src_path).resolve() == self.config_path:
            if self._reload_task:
                self._reload_task.cancel()
            self._reload_task = asyncio.run_coroutine_threadsafe(
                self._reload(), self.loop
            )

    async def _reload(self):
        await asyncio.sleep(0.3)
        try:
            old_rules = len(get_config().rules)
            new_config = load_config(self.config_path)
            logger.info(f"Config reloaded: {old_rules} → {len(new_config.rules)} rules")
        except Exception as e:
            logger.error(f"Config reload failed: {e}")


class ConfigWatcher:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.observer = Observer()

    def start(self, loop: asyncio.AbstractEventLoop):
        handler = ConfigFileHandler(self.config_path, loop)
        watch_dir = str(Path(self.config_path).parent.resolve())
        self.observer.schedule(handler, watch_dir, recursive=False)
        self.observer.start()
        logger.info(f"Watching config: {self.config_path}")

    def stop(self):
        self.observer.stop()
        self.observer.join()