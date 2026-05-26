import asyncio
import json
import importlib
from typing import Dict, List, Type
from redis.asyncio import Redis
from artha.interfaces.base import Strategy
from artha.schemas.models import Candle
from artha.core.logger import setup_logging, get_logger
from artha.core.heartbeat import Heartbeat
from artha.config.loader import config

setup_logging()
logger = get_logger("strategy_host")

class StrategyHost:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None
        self.strategies: Dict[str, Strategy] = {}
        self.tasks: List[asyncio.Task] = []

    async def start(self):
        self.redis = Redis.from_url(self.redis_url)
        
        # Load strategies from config
        strat_configs = config.get("strategies", [])
        for sc in strat_configs:
            if not sc.get("enabled", True):
                continue
            
            strat_id = sc["id"]
            # For simplicity, we assume the class name is CamelCase of the module name
            # or we could add a 'class' field to config.
            # Let's map it manually for now or use a convention.
            if strat_id == "ma_cross":
                module_path = "artha.strategies.ma_crossover"
                class_name = "MACrossoverStrategy"
            else:
                logger.error(f"Unknown strategy ID: {strat_id}")
                continue

            try:
                module = importlib.import_module(module_path)
                strat_class = getattr(module, class_name)
                strategy = strat_class(strat_id, sc.get("params", {}))
                self.strategies[strat_id] = strategy
                logger.info(f"Loaded strategy: {strat_id}")
            except Exception as e:
                logger.error(f"Failed to load strategy {strat_id}: {e}")

        # Start a task for each strategy to consume its relevant streams
        # For now, let's assume each strategy wants all crypto 15m candles
        # In a real system, we'd map symbols/tf per strategy.
        crypto_cfg = config.get("markets", {}).get("crypto", {})
        symbols = crypto_cfg.get("symbols", [])
        timeframes = crypto_cfg.get("timeframes", [])
        
        for symbol in symbols:
            for tf in timeframes:
                stream_name = f"candles:crypto:{symbol}:{tf}"
                self.tasks.append(asyncio.create_task(self._consume_stream(stream_name)))

        logger.info(f"StrategyHost started with {len(self.strategies)} strategies and {len(self.tasks)} consumers")

    async def _consume_stream(self, stream_name: str):
        """Consume candles from a Redis stream and dispatch to strategies."""
        # Use a consumer group to ensure we don't miss candles on restart
        group_name = "strategy_host_group"
        consumer_name = "host_1"
        
        try:
            await self.redis.xgroup_create(stream_name, group_name, id="0", mkstream=True)
        except Exception:
            pass # Already exists
            
        while True:
            try:
                # Read from stream
                messages = await self.redis.xreadgroup(group_name, consumer_name, {stream_name: ">"}, count=1, block=5000)
                if not messages:
                    continue
                
                for stream, msgs in messages:
                    for msg_id, data in msgs:
                        candle_json = data[b"data"]
                        candle = Candle.model_validate_json(candle_json)
                        
                        # Dispatch to all strategies
                        for strat_id, strategy in self.strategies.items():
                            try:
                                signal = await strategy.on_candle(candle)
                                if signal:
                                    # Publish signal to Redis
                                    await self.redis.xadd("signals", {"data": signal.model_dump_json()}, maxlen=1000, approximate=True)
                                    logger.info(f"Signal from {strat_id} published: {signal.signal_id}")
                            except Exception as e:
                                logger.error(f"Error in strategy {strat_id} on_candle: {e}")
                        
                        # Acknowledge message
                        await self.redis.xack(stream_name, group_name, msg_id)
                        
            except Exception as e:
                logger.error(f"Error consuming stream {stream_name}: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        if self.redis:
            await self.redis.close()

async def main():
    redis_url = config.get("redis", {}).get("url", "redis://localhost:6379")
    host = StrategyHost(redis_url)
    
    hb = Heartbeat(redis_url=redis_url, component_name="strategy-host")
    await hb.start()
    
    await host.start()
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await host.stop()
        await hb.stop()

if __name__ == "__main__":
    asyncio.run(main())
