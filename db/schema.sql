-- Quant Lab v2 Database Schema
-- Optimized for PostgreSQL + TimescaleDB

-- 1. Market Data (Hypertable)
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    open_price DOUBLE PRECISION NOT NULL,
    high_price DOUBLE PRECISION NOT NULL,
    low_price DOUBLE PRECISION NOT NULL,
    close_price DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, symbol, market, tf)
);

-- Convert to hypertable (requires TimescaleDB extension)
-- SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);

-- 2. Signals
CREATE TABLE IF NOT EXISTS signals (
    signal_id UUID PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    side TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    suggested_entry DOUBLE PRECISION NOT NULL,
    suggested_sl DOUBLE PRECISION NOT NULL,
    suggested_tp DOUBLE PRECISION NOT NULL,
    features JSONB DEFAULT '{}',
    candle_close_time TIMESTAMPTZ NOT NULL,
    emitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_v TEXT NOT NULL
);

-- 3. Decisions
CREATE TABLE IF NOT EXISTS decisions (
    decision_id UUID PRIMARY KEY,
    signal_id UUID NOT NULL REFERENCES signals(signal_id),
    verdict TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    llm_used BOOLEAN DEFAULT FALSE,
    llm_reasoning TEXT,
    sizing_hint DOUBLE PRECISION,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_v TEXT NOT NULL
);

-- 4. Positions
CREATE TABLE IF NOT EXISTS positions (
    trade_id UUID PRIMARY KEY,
    signal_id UUID NOT NULL REFERENCES signals(signal_id),
    decision_id UUID NOT NULL REFERENCES decisions(decision_id),
    strategy_id TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    mode TEXT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    stop_loss DOUBLE PRECISION NOT NULL,
    target DOUBLE PRECISION NOT NULL,
    trailing_cfg JSONB,
    status TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_v TEXT NOT NULL
);

-- 5. Exits
CREATE TABLE IF NOT EXISTS exits (
    trade_id UUID PRIMARY KEY REFERENCES positions(trade_id),
    exit_price DOUBLE PRECISION NOT NULL,
    exit_reason TEXT NOT NULL,
    pnl DOUBLE PRECISION NOT NULL,
    closed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    schema_v TEXT NOT NULL
);

-- 6. Shadow Positions (for TRACK mode)
CREATE TABLE IF NOT EXISTS shadow_positions (
    trade_id UUID PRIMARY KEY,
    signal_id UUID NOT NULL REFERENCES signals(signal_id),
    decision_id UUID NOT NULL REFERENCES decisions(decision_id),
    strategy_id TEXT NOT NULL,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    qty DOUBLE PRECISION NOT NULL,
    stop_loss DOUBLE PRECISION NOT NULL,
    target DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    exit_price DOUBLE PRECISION,
    pnl DOUBLE PRECISION,
    schema_v TEXT NOT NULL
);

-- 7. Trade Events (Append-only Audit Log)
CREATE TABLE IF NOT EXISTS trade_events (
    id SERIAL PRIMARY KEY,
    trade_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    event_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_market_data_lookup ON market_data (symbol, market, tf, time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals (strategy_id, emitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status);
CREATE INDEX IF NOT EXISTS idx_trade_events_id ON trade_events (trade_id);
