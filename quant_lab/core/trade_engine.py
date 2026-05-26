import uuid
from typing import Dict, Any, List, Optional
from quant_lab.schemas.models import Signal, Decision, Position, MarketMode, Side
from quant_lab.core.logger import get_logger

logger = get_logger(__name__)

class TradeEngine:
    """
    OMS — Orchestrates order execution and position registration.
    In Phase 3, it handles Paper trading by immediately "filling" orders.
    """
    def __init__(self, mode: MarketMode = MarketMode.PAPER):
        self.mode = mode

    async def execute(self, signal: Signal, decision: Decision, qty: float) -> Position:
        """
        Executes a trade and returns a Position object.
        """
        # In Paper mode, we assume immediate fill at suggested entry price
        logger.info(f"Executing {self.mode} trade for {signal.symbol} qty={qty}")
        
        return Position(
            signal_id=signal.signal_id,
            decision_id=decision.decision_id,
            strategy_id=signal.strategy_id,
            market=signal.market,
            symbol=signal.symbol,
            side=signal.side,
            mode=self.mode,
            entry_price=signal.suggested_entry,
            qty=qty,
            stop_loss=signal.suggested_sl,
            target=signal.suggested_tp,
            status="open"
        )
