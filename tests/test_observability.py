import pytest
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from artha.core.position_monitor import PositionMonitor
from artha.schemas.models import Position, Candle, MarketMode, Side

@pytest.mark.asyncio
async def test_event_emission():
    # Mock Redis and Repo
    redis = AsyncMock()
    repo = AsyncMock()
    monitor = PositionMonitor(repo, redis)
    
    pos = Position(
        strategy_id="test", market="crypto", symbol="BTCUSDT", tf="15m",
        side=Side.LONG, mode=MarketMode.PAPER, entry_price=50000.0,
        qty=1.0, stop_loss=49000.0, target=52000.0,
        signal_id=uuid.uuid4(),
        decision_id=uuid.uuid4()
    )
    monitor.add_position(pos)
    
    # Tick that hits Target
    tp_tick = Candle(
        market="crypto", symbol="BTCUSDT", tf="1m",
        open_time=datetime.now(timezone.utc), close_time=datetime.now(timezone.utc),
        o=52500, h=52500, l=52500, c=52500, v=0, source="test"
    )
    await monitor.on_tick(tp_tick)
    
    # Verify event emission
    redis.xadd.assert_called_once()
    args, kwargs = redis.xadd.call_args
    assert args[0] == "events"
    fields = args[1]
    data = json.loads(fields['data'])
    assert data['type'] == "POSITION_CLOSED"
    assert data['symbol'] == "BTCUSDT"
    assert data['reason'] == "target"
    assert data['pnl'] == 2500.0
