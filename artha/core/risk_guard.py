from typing import Optional, Tuple
from artha.schemas.models import Signal, Decision, Verdict
from artha.core.logger import get_logger

logger = get_logger(__name__)

class RiskGuard:
    """
    Fail-closed gate for approved signals.
    Calculates risk-based sizing and enforces portfolio limits.
    """
    def __init__(self, config: dict):
        self.config = config
        self.max_concurrent = config.get("max_concurrent_positions", 5)
        self.risk_per_trade_pct = config.get("max_risk_per_trade_pct", 0.01)
        self.total_capital = config.get("total_capital", 100000.0) # Dummy 1L capital

    async def validate(self, signal: Signal, decision: Decision, open_count: int) -> Tuple[bool, str, float]:
        """
        Validates a TAKE decision against risk rules.
        Returns: (is_allowed, reason, qty)
        """
        # 1. Concurrent positions
        if open_count >= self.max_concurrent:
            return False, "MAX_CONCURRENT_EXCEEDED", 0.0
            
        # 2. Daily Loss check (stubbed - requires PnL tracker)
        # if self.pnl_tracker.daily_loss_pct > self.config['max_daily_loss_pct']:
        #     return False, "DAILY_LOSS_BREACH", 0.0

        # 3. Risk-based sizing
        # qty = (capital * risk_pct) / |entry - SL|
        stop_dist = abs(signal.suggested_entry - signal.suggested_sl)
        if stop_dist == 0:
            return False, "INVALID_STOP_DISTANCE", 0.0
            
        risk_amount = self.total_capital * self.risk_per_trade_pct
        qty = risk_amount / stop_dist
        
        # Apply sizing hint from Decision Agent
        if decision.sizing_hint:
            qty *= decision.sizing_hint
            
        logger.info(f"Risk Guard approved: {signal.symbol} qty={qty:.4f}")
        return True, "ALLOWED", qty
