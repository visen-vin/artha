import asyncio
import json
from datetime import datetime, timezone, timedelta
from redis.asyncio import Redis
from artha.core.logger import setup_logging, get_logger
from artha.core.heartbeat import Heartbeat
from artha.config.loader import config

setup_logging()
logger = get_logger("watchdog")

class Watchdog:
    def __init__(self, redis_url: str, check_interval: int = 10, stale_threshold: int = 15):
        self.redis_url = redis_url
        self.check_interval = check_interval
        self.stale_threshold = stale_threshold
        self.redis: Optional[Redis] = None
        self._running = False

    async def start(self):
        self.redis = Redis.from_url(self.redis_url)
        self._running = True
        logger.info("Watchdog started.")
        asyncio.create_task(self._loop())

    async def _loop(self):
        while self._running:
            try:
                heartbeats = await self.redis.hgetall("heartbeats")
                now = datetime.now(timezone.utc)
                
                for component, data_json in heartbeats.items():
                    data = json.loads(data_json)
                    ts = datetime.fromisoformat(data["timestamp"])
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                        
                    diff = (now - ts).total_seconds()
                    
                    if diff > self.stale_threshold:
                        logger.error(f"STALE HEARTBEAT: {component.decode()} last seen {diff:.1f}s ago!")
                        # Alert via Telegram (Emit an event)
                        event = {
                            "type": "SERVICE_DOWN",
                            "component": component.decode(),
                            "last_seen": data["timestamp"],
                            "diff_seconds": diff,
                            "timestamp": now.isoformat()
                        }
                        await self.redis.xadd("events", {"data": json.dumps(event)}, maxlen=1000, approximate=True)
                
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
                await asyncio.sleep(self.check_interval)

    async def stop(self):
        self._running = False
        if self.redis:
            await self.redis.close()

async def main():
    redis_url = config.get("redis", {}).get("url", "redis://localhost:6379")
    dog = Watchdog(redis_url)
    
    hb = Heartbeat(redis_url=redis_url, component_name="watchdog")
    await hb.start()
    
    await dog.start()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await dog.stop()
        await hb.stop()

if __name__ == "__main__":
    asyncio.run(main())
