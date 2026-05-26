import asyncio
import asyncpg
from redis.asyncio import Redis
from artha.schemas.models import Signal, Candle, Verdict
from artha.db.repositories.ledger import LedgerRepository
from artha.core.decision_agent_orchestrator import DecisionAgent
from artha.core.risk_guard import RiskGuard
from artha.core.trade_engine import TradeEngine
from artha.core.position_monitor import PositionMonitor
from artha.core.logger import setup_logging, get_logger
from artha.core.heartbeat import Heartbeat
from artha.config.loader import config

setup_logging()
logger = get_logger("core_engine")

class CoreEngine:
    def __init__(self, redis_url: str, db_url: str):
        self.redis_url = redis_url
        self.db_url = db_url
        self.redis = None
        self.pool = None
        self.repo = None
        self.agent = None
        self.risk = None
        self.trade = None
        self.monitor = None

    async def start(self):
        self.redis = Redis.from_url(self.redis_url)
        self.pool = await asyncpg.create_pool(self.db_url)
        self.repo = LedgerRepository(self.pool)
        
        self.agent = DecisionAgent(config.get("llm", {}))
        self.risk = RiskGuard(config.get("risk", {}))
        self.trade = TradeEngine()
        self.monitor = PositionMonitor(self.repo, self.redis)
        
        # Load open positions to monitor (crash recovery)
        # TODO: Implement full recovery from DB rows
        
        # Start consumers
        asyncio.create_task(self._consume_signals())
        asyncio.create_task(self._consume_ticks())
        
        logger.info("Core Engine started (Money-path fused)")

    async def _consume_signals(self):
        """Consume signals -> Decision -> Risk -> Execute."""
        group_name = "core_engine_signals"
        stream_name = "signals"
        try:
            await self.redis.xgroup_create(stream_name, group_name, id="0", mkstream=True)
        except Exception:
            pass
            
        while True:
            try:
                messages = await self.redis.xreadgroup(group_name, "core_1", {stream_name: ">"}, count=1, block=5000)
                if not messages:
                    continue
                
                for stream, msgs in messages:
                    for msg_id, data in msgs:
                        signal = Signal.model_validate_json(data[b"data"])
                        await self.repo.save_signal(signal)
                        
                        # 1. Decision Agent (Guru Ji)
                        decision = await self.agent.decide(signal)
                        await self.repo.save_decision(decision)
                        
                        if decision.verdict == Verdict.TAKE:
                            # 2. Risk Guard
                            open_count = len(self.monitor.open_positions)
                            allowed, reason, qty = await self.risk.validate(signal, decision, open_count)
                            
                            if allowed:
                                # 3. Trade Engine (Execute)
                                position = await self.trade.execute(signal, decision, qty)
                                await self.repo.save_position(position)
                                
                                # 4. Position Monitor (Watch)
                                self.monitor.add_position(position)
                                
                                # 5. Emit Event
                                event = {
                                    "type": "POSITION_OPENED",
                                    "symbol": position.symbol,
                                    "side": position.side,
                                    "qty": position.qty,
                                    "entry": position.entry_price,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                                await self.redis.xadd("events", {"data": json.dumps(event)}, maxlen=1000, approximate=True)
                            else:
                                logger.warning(f"Trade REJECTED by Risk Guard: {reason}")
                        elif decision.verdict == Verdict.TRACK:
                            # Shadow trading / Tracking
                            logger.info(f"TRACKing signal {signal.signal_id} for {signal.symbol}")
                            # TODO: Implement shadow_positions in PositionMonitor
                        
                        await self.redis.xack(stream_name, group_name, msg_id)
                        
            except Exception as e:
                logger.error(f"Error in signal consumer: {e}")
                await asyncio.sleep(1)

    async def _consume_ticks(self):
        """Consume low-latency price ticks for auto-cut."""
        # Use Pub/Sub for fast prices
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("prices:*")
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                try:
                    candle = Candle.model_validate_json(message["data"])
                    await self.monitor.on_tick(candle)
                except Exception as e:
                    logger.error(f"Error in tick consumer: {e}")

    async def stop(self):
        if self.redis:
            await self.redis.close()
        if self.pool:
            await self.pool.close()

async def main():
    redis_url = config.get("redis", {}).get("url", "redis://localhost:6379")
    db_url = config.get("postgres", {}).get("url")
    
    engine = CoreEngine(redis_url, db_url)
    
    hb = Heartbeat(redis_url=redis_url, component_name="core-engine")
    await hb.start()
    
    await engine.start()
    
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        await engine.stop()
        await hb.stop()

if __name__ == "__main__":
    asyncio.run(main())
