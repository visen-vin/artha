import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, UUID4

class Side(str, Enum):
    LONG = "long"
    SHORT = "short"

class MarketMode(str, Enum):
    LIVE = "live"
    PAPER = "paper"
    SHADOW = "shadow"

class ExitReason(str, Enum):
    SL = "sl"
    TARGET = "target"
    TRAILING = "trailing"
    SQUARE_OFF = "square_off"
    MANUAL = "manual"

class Verdict(str, Enum):
    TAKE = "take"
    REJECT = "reject"
    TRACK = "track"

class BaseMessage(BaseModel):
    schema_v: str = "2.0.0"

class Candle(BaseMessage):
    market: str
    symbol: str
    tf: str
    open_time: datetime
    close_time: datetime
    o: float
    h: float
    l: float
    c: float
    v: float
    closed: bool = True
    source: str

class Signal(BaseMessage):
    signal_id: UUID4 = Field(default_factory=uuid.uuid4)
    strategy_id: str
    market: str
    symbol: str
    tf: str
    side: Side
    confidence: float # 0..1
    suggested_entry: float
    suggested_sl: float
    suggested_tp: float
    features: Dict[str, Any] = {}
    candle_close_time: datetime
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Decision(BaseMessage):
    decision_id: UUID4 = Field(default_factory=uuid.uuid4)
    signal_id: UUID4
    verdict: Verdict
    reason_code: str
    llm_used: bool = False
    llm_reasoning: Optional[str] = None
    sizing_hint: Optional[float] = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Position(BaseMessage):
    trade_id: UUID4 = Field(default_factory=uuid.uuid4)
    signal_id: UUID4
    decision_id: UUID4
    strategy_id: str
    market: str
    symbol: str
    side: Side
    mode: MarketMode
    entry_price: float
    qty: float
    stop_loss: float
    target: float
    trailing_cfg: Optional[Dict[str, Any]] = None
    status: str = "open" # open, closed, exiting, pending
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Exit(BaseMessage):
    trade_id: UUID4
    exit_price: float
    exit_reason: ExitReason
    pnl: float
    closed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
