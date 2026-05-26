import pytest
from datetime import datetime, timezone
from uuid import UUID
from artha.schemas.models import Candle, Signal, Side

def test_candle_schema():
    candle = Candle(
        market="crypto",
        symbol="BTCUSDT",
        tf="15m",
        open_time=datetime.now(timezone.utc),
        close_time=datetime.now(timezone.utc),
        o=50000.0,
        h=51000.0,
        l=49000.0,
        c=50500.0,
        v=100.0,
        source="binance"
    )
    assert candle.symbol == "BTCUSDT"
    assert candle.schema_v == "2.0.0"

def test_signal_schema():
    signal = Signal(
        strategy_id="test_strat",
        market="crypto",
        symbol="BTCUSDT",
        tf="15m",
        side=Side.LONG,
        confidence=0.8,
        suggested_entry=50000.0,
        suggested_sl=49000.0,
        suggested_tp=52000.0,
        candle_close_time=datetime.now(timezone.utc)
    )
    assert signal.side == "long"
    assert isinstance(signal.signal_id, UUID)
