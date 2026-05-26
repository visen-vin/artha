import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from artha.schemas.models import Signal, Side, Verdict, Candle
from artha.core.decision_agent_orchestrator import DecisionAgent
from artha.core.risk_guard import RiskGuard
from artha.core.trade_engine import TradeEngine
from artha.core.position_monitor import PositionMonitor

@pytest.mark.asyncio
async def test_money_path_logic():
    # 1. Decision Agent
    agent = DecisionAgent({"min_confidence": 0.7})
    signal = Signal(
        strategy_id="test", market="crypto", symbol="BTCUSDT", tf="15m",
        side=Side.LONG, confidence=0.95, suggested_entry=50000.0,
        suggested_sl=49000.0, suggested_tp=52000.0,
        candle_close_time=datetime.now(timezone.utc)
    )
    decision = await agent.decide(signal)
    assert decision.verdict == Verdict.TAKE

    # 2. Risk Guard
    risk = RiskGuard({"max_concurrent_positions": 5, "max_risk_per_trade_pct": 0.01, "total_capital": 100000.0})
    allowed, reason, qty = await risk.validate(signal, decision, 0)
    assert allowed is True
    # risk_amount = 1000, stop_dist = 1000 -> qty = 1.0
    assert qty == 1.0

    # 3. Trade Engine
    engine = TradeEngine()
    position = await engine.execute(signal, decision, qty)
    assert position.status == "open"
    assert position.qty == 1.0

    # 4. Position Monitor (Auto-cut)
    repo = MagicMock()
    repo.close_position = AsyncMock()
    redis = AsyncMock()
    monitor = PositionMonitor(repo, redis)
    monitor.add_position(position)
    
    # Tick that hits SL
    sl_tick = Candle(
        market="crypto", symbol="BTCUSDT", tf="1m",
        open_time=datetime.now(timezone.utc), close_time=datetime.now(timezone.utc),
        o=48500, h=48500, l=48500, c=48500, v=0, source="test"
    )
    await monitor.on_tick(sl_tick)
    
    assert len(monitor.open_positions) == 0
    repo.close_position.assert_called_once()
    exit_call = repo.close_position.call_args[0][0]
    assert exit_call.exit_reason == "sl"
    assert exit_call.pnl == -1500.0 # (48500 - 50000) * 1.0
