import asyncpg
from typing import List
from artha.schemas.models import Candle
from artha.core.logger import get_logger

logger = get_logger(__name__)

class MarketDataRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def upsert_candle(self, candle: Candle):
        query = """
        INSERT INTO market_data (
            time, market, symbol, tf, open_price, high_price, low_price, close_price, volume, source
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (time, symbol, market, tf) DO UPDATE SET
            open_price = EXCLUDED.open_price,
            high_price = EXCLUDED.high_price,
            low_price = EXCLUDED.low_price,
            close_price = EXCLUDED.close_price,
            volume = EXCLUDED.volume,
            source = EXCLUDED.source;
        """
        # Note: The ON CONFLICT requires a unique constraint on (time, symbol, market, tf)
        # We should update the schema to include this.
        try:
            await self.pool.execute(
                query,
                candle.open_time,
                candle.market,
                candle.symbol,
                candle.tf,
                candle.o,
                candle.h,
                candle.l,
                candle.c,
                candle.v,
                candle.source
            )
        except Exception as e:
            logger.error(f"Failed to upsert candle for {candle.symbol}: {e}")

    async def upsert_candles(self, candles: List[Candle]):
        if not candles:
            return
        
        # Simple bulk insert
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for candle in candles:
                    await self.upsert_candle(candle)
        logger.info(f"Bulk upserted {len(candles)} candles.")
