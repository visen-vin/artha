import asyncpg
from uuid import UUID
from typing import Optional
from artha.schemas.models import Signal, Decision, Position, Exit
from artha.core.logger import get_logger

logger = get_logger(__name__)

class LedgerRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save_signal(self, signal: Signal):
        query = """
        INSERT INTO signals (
            signal_id, strategy_id, market, symbol, tf, side, confidence, 
            suggested_entry, suggested_sl, suggested_tp, features, 
            candle_close_time, emitted_at, schema_v
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (signal_id) DO NOTHING;
        """
        await self.pool.execute(
            query,
            signal.signal_id, signal.strategy_id, signal.market, signal.symbol, signal.tf,
            signal.side, signal.confidence, signal.suggested_entry, signal.suggested_sl,
            signal.suggested_tp, signal.model_dump_json(include={'features'}),
            signal.candle_close_time, signal.emitted_at, signal.schema_v
        )

    async def save_decision(self, decision: Decision):
        query = """
        INSERT INTO decisions (
            decision_id, signal_id, verdict, reason_code, llm_used, 
            llm_reasoning, sizing_hint, decided_at, schema_v
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9);
        """
        await self.pool.execute(
            query,
            decision.decision_id, decision.signal_id, decision.verdict,
            decision.reason_code, decision.llm_used, decision.llm_reasoning,
            decision.sizing_hint, decision.decided_at, decision.schema_v
        )

    async def save_position(self, pos: Position):
        query = """
        INSERT INTO positions (
            trade_id, signal_id, decision_id, strategy_id, market, symbol, 
            side, mode, entry_price, qty, stop_loss, target, 
            trailing_cfg, status, opened_at, schema_v
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        ON CONFLICT (trade_id) DO UPDATE SET status = EXCLUDED.status;
        """
        await self.pool.execute(
            query,
            pos.trade_id, pos.signal_id, pos.decision_id, pos.strategy_id,
            pos.market, pos.symbol, pos.side, pos.mode, pos.entry_price,
            pos.qty, pos.stop_loss, pos.target, 
            pos.model_dump_json(include={'trailing_cfg'}),
            pos.status, pos.opened_at, pos.schema_v
        )

    async def close_position(self, exit_data: Exit, final_status: str = "closed"):
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Update position status
                await conn.execute(
                    "UPDATE positions SET status = $1 WHERE trade_id = $2",
                    final_status, exit_data.trade_id
                )
                # 2. Insert exit record
                query = """
                INSERT INTO exits (
                    trade_id, exit_price, exit_reason, pnl, closed_at, schema_v
                ) VALUES ($1, $2, $3, $4, $5, $6);
                """
                await conn.execute(
                    query,
                    exit_data.trade_id, exit_data.exit_price, exit_data.exit_reason,
                    exit_data.pnl, exit_data.closed_at, exit_data.schema_v
                )

    async def get_open_positions(self) -> list[Position]:
        rows = await self.pool.fetch("SELECT * FROM positions WHERE status IN ('open', 'exiting', 'pending')")
        # In a real implementation, we'd map these rows back to Position models.
        # This requires a bit of mapping logic for UUIDs and JSONBs.
        return rows # Placeholder
