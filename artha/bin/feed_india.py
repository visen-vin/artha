import asyncio
from artha.core.logger import setup_logging, get_logger
from artha.core.heartbeat import Heartbeat

setup_logging()
logger = get_logger("feed_india")

async def main():
    logger.info("service starting...")
    # In a real scenario, we would load config here
    hb = Heartbeat(redis_url="redis://localhost:6379", component_name="feed_india")
    await hb.start()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await hb.stop()
        logger.info("service stopping...")

if __name__ == "__main__":
    asyncio.run(main())
