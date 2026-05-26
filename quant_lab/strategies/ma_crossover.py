import polars as pl
from typing import Optional, Dict, Any
from datetime import datetime
from quant_lab.interfaces.base import Strategy
from quant_lab.schemas.models import Candle, Signal, Side
from quant_lab.core.logger import get_logger

logger = get_logger(__name__)

class MACrossoverStrategy(Strategy):
    """
    Simple Moving Average Crossover Strategy.
    Emits a LONG signal when fast MA crosses above slow MA.
    Emits a SHORT signal when fast MA crosses below slow MA.
    """
    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        super().__init__(strategy_id, config)
        self.fast_period = config.get("fast_period", 9)
        self.slow_period = config.get("slow_period", 21)
        self.history: Dict[str, pl.DataFrame] = {} # symbol -> df

    def get_warmup_candles(self) -> int:
        return self.slow_period + 5 # Buffer

    async def on_candle(self, candle: Candle) -> Optional[Signal]:
        symbol = candle.symbol
        
        # 1. Update history
        new_row = {
            "time": candle.open_time,
            "close": candle.c
        }
        
        if symbol not in self.history:
            self.history[symbol] = pl.DataFrame([new_row])
        else:
            self.history[symbol] = pl.concat([self.history[symbol], pl.DataFrame([new_row])])
            
        # Limit history size
        max_len = self.slow_period + 2
        if len(self.history[symbol]) > max_len:
            self.history[symbol] = self.history[symbol].tail(max_len)

        if len(self.history[symbol]) < self.slow_period + 1:
            return None

        # 2. Calculate MAs
        df = self.history[symbol].with_columns([
            pl.col("close").ewm_mean(span=self.fast_period).alias("fast_ma"),
            pl.col("close").ewm_mean(span=self.slow_period).alias("slow_ma")
        ])
        
        # 3. Check crossover
        prev_fast = df["fast_ma"][-2]
        prev_slow = df["slow_ma"][-2]
        curr_fast = df["fast_ma"][-1]
        curr_slow = df["slow_ma"][-1]
        
        side = None
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            side = Side.LONG
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            side = Side.SHORT
            
        if side:
            logger.info(f"Signal generated: {side} for {symbol}")
            # Simplified SL/TP for v1
            sl_pct = 0.02
            tp_pct = 0.04
            
            entry = candle.c
            sl = entry * (1 - sl_pct) if side == Side.LONG else entry * (1 + sl_pct)
            tp = entry * (1 + tp_pct) if side == Side.LONG else entry * (1 - tp_pct)
            
            return Signal(
                strategy_id=self.strategy_id,
                market=candle.market,
                symbol=symbol,
                tf=candle.tf,
                side=side,
                confidence=1.0,
                suggested_entry=entry,
                suggested_sl=sl,
                suggested_tp=tp,
                candle_close_time=candle.close_time,
                features={
                    "fast_ma": curr_fast,
                    "slow_ma": curr_slow
                }
            )
            
        return None
