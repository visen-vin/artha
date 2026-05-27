import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import aiohttp
from artha.interfaces.base import MarketAdapter
from artha.schemas.models import Candle
from artha.core.logger import get_logger

logger = get_logger(__name__)

class BinanceAdapter(MarketAdapter):
    BASE_URL = "https://api.binance.com"
    WS_URL = "wss://stream.binance.com:9443/ws"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        logger.info("BinanceAdapter connected (session initialized)")

    async def disconnect(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def fetch_historical_candles(self, symbol: str, interval: str, limit: int = 500) -> List[Candle]:
        """Fetch historical klines from Binance REST API."""
        url = f"{self.BASE_URL}/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        async with self.session.get(url, params=params) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                logger.error(f"Failed to fetch historical candles for {symbol}: {error_text}")
                return []
            
            data = await resp.json()
            return [self._map_rest_candle(symbol, interval, k) for k in data]

    def _map_rest_candle(self, symbol: str, interval: str, kline: list) -> Candle:
        """
        Map Binance REST kline list to Candle model.
        Binance kline format: [Open time, Open, High, Low, Close, Volume, Close time, ...]
        """
        return Candle(
            market="crypto",
            symbol=symbol,
            tf=interval,
            open_time=datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
            close_time=datetime.fromtimestamp(kline[6] / 1000, tz=timezone.utc),
            o=float(kline[1]),
            h=float(kline[2]),
            l=float(kline[3]),
            c=float(kline[4]),
            v=float(kline[5]),
            closed=True,
            source="binance_rest"
        )

    def normalize(self, raw_data: Any) -> Candle:
        """Normalize Binance WS kline message."""
        # raw_data is expected to be a dict from WS stream
        k = raw_data.get('k', {})
        return Candle(
            market="crypto",
            symbol=raw_data.get('s'),
            tf=k.get('i'),
            open_time=datetime.fromtimestamp(k.get('t') / 1000, tz=timezone.utc),
            close_time=datetime.fromtimestamp(k.get('T') / 1000, tz=timezone.utc),
            o=float(k.get('o')),
            h=float(k.get('h')),
            l=float(k.get('l')),
            c=float(k.get('c')),
            v=float(k.get('v')),
            closed=k.get('x', False),
            source="binance_ws"
        )

    async def subscribe(self, symbols: List[str], timeframes: List[str]):
        """
        In this adapter, subscribe returns an async generator for the WS stream.
        """
        streams = "/".join([f"{s.lower()}@kline_{tf}" for s in symbols for tf in timeframes])
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(url) as ws:
                logger.info(f"Subscribed to Binance streams: {streams}")
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        # For /stream URL, data is wrapped in {"stream": "...", "data": {...}}
                        payload = data.get("data", data)
                        yield self.normalize(payload)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"WS connection closed with error: {ws.exception()}")
                        break

    def session_info(self, symbol: str) -> Dict[str, Any]:
        # Crypto is 24/7
        return {
            "is_open": True,
            "timezone": "UTC"
        }
