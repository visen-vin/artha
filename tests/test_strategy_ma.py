import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from artha.strategies.ma_crossover import MACrossoverStrategy
from artha.schemas.models import Candle

@pytest.mark.asyncio
async def test_ma_crossover_logic():
    strategy = MACrossoverStrategy("test_ma", {"fast_period": 2, "slow_period": 4})
    
    # Generate mock candles to trigger a LONG crossover
    # Fast MA (2) will catch up to Slow MA (4)
    prices = [10, 10, 10, 10, 12, 14, 16]
    signals = []
    
    start_time = datetime.now(timezone.utc)
    for i, p in enumerate(prices):
        candle = Candle(
            market="crypto",
            symbol="BTCUSDT",
            tf="15m",
            open_time=start_time + timedelta(minutes=15*i),
            close_time=start_time + timedelta(minutes=15*i + 14),
            o=p, h=p, l=p, c=p, v=100,
            source="test"
        )
        signal = await strategy.on_candle(candle)
        if signal:
            signals.append(signal)
            
    assert len(signals) > 0
    assert signals[0].side == "long"
