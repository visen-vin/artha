from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from artha.schemas.models import Candle, Signal, Position

class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        pass

    @abstractmethod
    def sleep(self, seconds: float):
        pass

class MarketAdapter(ABC):
    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def subscribe(self, symbols: List[str], timeframes: List[str]):
        pass

    @abstractmethod
    def normalize(self, raw_data: Any) -> Candle:
        pass

    @abstractmethod
    def session_info(self, symbol: str) -> Dict[str, Any]:
        pass

class ExecutionAdapter(ABC):
    @abstractmethod
    async def place_order(self, position: Position) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        pass

    @abstractmethod
    async def close_position(self, trade_id: str, price: Optional[float] = None) -> Dict[str, Any]:
        pass

class Strategy(ABC):
    def __init__(self, strategy_id: str, config: Dict[str, Any]):
        self.strategy_id = strategy_id
        self.config = config

    @abstractmethod
    async def on_candle(self, candle: Candle) -> Optional[Signal]:
        pass

    @abstractmethod
    def get_warmup_candles(self) -> int:
        pass
