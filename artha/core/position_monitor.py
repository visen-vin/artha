import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from redis.asyncio import Redis
from artha.schemas.models import Position, Candle, Exit, Side, ExitReason
from artha.db.repositories.ledger import LedgerRepository
from artha.core.logger import get_logger

logger = get_logger(__name__)

class PositionMonitor:
    """
    The auto-cut loop. 
    Watches open positions on every price tick and triggers exits.
    """
    def __init__(self, repo: LedgerRepository, redis: Redis):
        self.repo = repo
        self.redis = redis
        self.open_positions: Dict[str, Position] = {} # trade_id -> Position

    def add_position(self, pos: Position):
        self.open_positions[str(pos.trade_id)] = pos
        logger.info(f"Monitor: Watching {pos.symbol} {pos.side} for trade {pos.trade_id}")

    async def on_tick(self, candle: Candle):
        """Processes a price tick (fast price) for potential exits."""
        symbol = candle.symbol
        price = candle.c # Current price
        
        exits_to_process = []
        
        for tid, pos in self.open_positions.items():
            if pos.symbol != symbol:
                continue
                
            trigger_reason = None
            if pos.side == Side.LONG:
                if price <= pos.stop_loss:
                    trigger_reason = ExitReason.SL
                elif price >= pos.target:
                    trigger_reason = ExitReason.TARGET
            else: # SHORT
                if price >= pos.stop_loss:
                    trigger_reason = ExitReason.SL
                elif price <= pos.target:
                    trigger_reason = ExitReason.TARGET
                    
            if trigger_reason:
                exits_to_process.append((tid, price, trigger_reason))

        for tid, exit_price, reason in exits_to_process:
            await self._process_exit(tid, exit_price, reason)

    async def _process_exit(self, trade_id: str, exit_price: float, reason: ExitReason):
        pos = self.open_positions.pop(trade_id)
        
        # Calculate PnL
        if pos.side == Side.LONG:
            pnl = (exit_price - pos.entry_price) * pos.qty
        else:
            pnl = (pos.entry_price - exit_price) * pos.qty
            
        exit_data = Exit(
            trade_id=pos.trade_id,
            exit_price=exit_price,
            exit_reason=reason,
            pnl=pnl
        )
        
        await self.repo.close_position(exit_data)
        logger.info(f"Auto-cut triggered: {pos.symbol} {reason} PnL={pnl:.2f}")

        # Emit Event
        event = {
            "type": "POSITION_CLOSED",
            "symbol": pos.symbol,
            "reason": reason,
            "exit_price": exit_price,
            "pnl": pnl,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await self.redis.xadd("events", {"data": json.dumps(event)}, maxlen=1000, approximate=True)
