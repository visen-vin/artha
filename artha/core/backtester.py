import asyncio
import asyncpg
import polars as pl
from datetime import datetime
from typing import List, Dict, Any, Optional
from artha.interfaces.base import Strategy, Clock
from artha.schemas.models import Candle, Signal, Side
from artha.core.logger import setup_logging, get_logger
from artha.config.loader import config

setup_logging()
logger = get_logger("backtester")

class SimulatedClock(Clock):
    def __init__(self, start_time: datetime):
        self.current_time = start_time

    def now(self) -> datetime:
        return self.current_time

    def set_time(self, new_time: datetime):
        self.current_time = new_time

    def sleep(self, seconds: float):
        # In simulation, sleep just advances the clock if we want to simulate delays
        pass

class Backtester:
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None

    async def run(self, strategy: Strategy, market: str, symbol: str, tf: str, start_date: datetime, end_date: datetime):
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.db_url)

        logger.info(f"Starting backtest for {strategy.strategy_id} on {symbol} {tf} from {start_date} to {end_date}")
        
        # 1. Fetch historical data from Postgres
        query = """
        SELECT time, market, symbol, tf, open_price, high_price, low_price, close_price, volume, source
        FROM market_data
        WHERE market = $1 AND symbol = $2 AND tf = $3 AND time >= $4 AND time <= $5
        ORDER BY time ASC
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, market, symbol, tf, start_date, end_date)
            
        if not rows:
            logger.warning("No data found for backtest range.")
            return []

        candles = [
            Candle(
                market=r['market'],
                symbol=r['symbol'],
                tf=r['tf'],
                open_time=r['time'],
                close_time=r['time'], # Simplified
                o=r['open_price'],
                h=r['high_price'],
                l=r['low_price'],
                c=r['close_price'],
                v=r['volume'],
                source=r['source']
            ) for r in rows
        ]
        
        logger.info(f"Replaying {len(candles)} candles...")
        
        # 2. Replay loop
        signals: List[Signal] = []
        clock = SimulatedClock(start_date)
        
        for candle in candles:
            clock.set_time(candle.open_time)
            signal = await strategy.on_candle(candle)
            if signal:
                signals.append(signal)
                logger.info(f"Backtest Signal: {signal.side} @ {signal.suggested_entry} at {candle.open_time}")

        logger.info(f"Backtest complete. Total signals: {len(signals)}")
        return signals

async def example_backtest():
    # Example usage
    from artha.strategies.ma_crossover import MACrossoverStrategy
    
    db_url = config.get("postgres", {}).get("url")
    tester = Backtester(db_url)
    
    strategy = MACrossoverStrategy("ma_cross_backtest", {"fast_period": 9, "slow_period": 21})
    
    start = datetime(2024, 1, 1)
    end = datetime(2026, 12, 31)
    
    signals = await tester.run(strategy, "crypto", "BTCUSDT", "15m", start, end)
    
    # In a full backtest, we would also run these signals through the Trade Engine logic.
    # That will come in Phase 3.

if __name__ == "__main__":
    asyncio.run(example_backtest())
