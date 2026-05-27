import asyncio
import json
import asyncpg
from redis.asyncio import Redis
from artha.feeds.binance import BinanceAdapter
from artha.db.repositories.market_data import MarketDataRepository
from artha.core.logger import setup_logging, get_logger
from artha.core.heartbeat import Heartbeat
from artha.config.loader import config

setup_logging()
logger = get_logger("feed_crypto")

async def main():
    logger.info("Crypto Feed starting...")
    
    # 1. Initialize dependencies
    adapter = BinanceAdapter()
    await adapter.connect()
    
    redis_url = config.get("redis", {}).get("url", "redis://localhost:6379")
    redis = Redis.from_url(redis_url)
    
    db_url = config.get("postgres", {}).get("url")
    pool = await asyncpg.create_pool(db_url)
    repo = MarketDataRepository(pool)
    
    hb = Heartbeat(redis_url=redis_url, component_name="feed-crypto")
    await hb.start()
    
    # 2. Warm-up / Backfill
    crypto_cfg = config.get("markets", {}).get("crypto", {})
    symbols = crypto_cfg.get("symbols", [])
    timeframes = crypto_cfg.get("timeframes", [])
    
    for symbol in symbols:
        for tf in timeframes:
            logger.info(f"Warming up {symbol} {tf}...")
            candles = await adapter.fetch_historical_candles(symbol, tf, limit=100)
            if candles:
                await repo.upsert_candles(candles)
    
    # 3. Stream loop
    logger.info("Entering stream loop...")
    try:
        while True:
            try:
                async for candle in adapter.subscribe(symbols, timeframes):
                    # Normalize and publish
                    # Only publish closed candles to the primary candle stream
                    if candle.closed:
                        stream_name = f"candles:crypto:{candle.symbol}:{candle.tf}"
                        await redis.xadd(stream_name, {"data": candle.model_dump_json()}, maxlen=1000, approximate=True)
                        
                        # Persist to DB
                        await repo.upsert_candle(candle)
                        logger.debug(f"Published closed candle for {candle.symbol} {candle.tf}")
                    else:
                        # Fast ticks / unclosed candles to Pub/Sub
                        channel_name = f"prices:crypto:{candle.symbol}"
                        await redis.publish(channel_name, candle.model_dump_json())
            except Exception as e:
                logger.error(f"Stream dropped, reconnecting in 5s... Error: {e}")
                await asyncio.sleep(5)
                
    except asyncio.CancelledError:
        logger.info("Crypto Feed stopping...")
    except Exception as e:
        logger.error(f"Crypto Feed error: {e}")
    finally:
        await hb.stop()
        await adapter.disconnect()
        await redis.close()
        await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
