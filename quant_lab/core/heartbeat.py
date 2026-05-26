import asyncio
import json
import time
from datetime import datetime
from redis.asyncio import Redis
from quant_lab.core.logger import get_logger

logger = get_logger(__name__)

class Heartbeat:
    def __init__(self, redis_url: str, component_name: str, interval: int = 5):
        self.redis_url = redis_url
        self.component_name = component_name
        self.interval = interval
        self.redis = None
        self._running = False
        self._task = None

    async def start(self):
        self.redis = Redis.from_url(self.redis_url)
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Heartbeat started for {self.component_name}")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.redis:
            await self.redis.close()
        logger.info(f"Heartbeat stopped for {self.component_name}")

    async def _loop(self):
        while self._running:
            try:
                hb_data = {
                    "component": self.component_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "alive"
                }
                await self.redis.hset("heartbeats", self.component_name, json.dumps(hb_data))
                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"Heartbeat error for {self.component_name}: {e}")
                await asyncio.sleep(self.interval)
