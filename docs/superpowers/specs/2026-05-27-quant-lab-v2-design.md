# Quant Lab v2 — Design & PRD

**Status:** Approved design (pre-implementation)
**Date:** 2026-05-27
**Supersedes:** `iron-v2-architecture.md`, `quant-lab-v2-prd.md` (both in `.gemini/tmp/`, ephemeral)

---

## 1. Vision & Scope

A **greenfield, Python-only, paper-first systematic-trading research lab** running on a single cheap VPS. Strategies run as parallel plugins on a streamed data feed; an AI decision agent ("Guru Ji") verdicts each signal as **TAKE / REJECT / TRACK**; approved trades are registered in a trade engine that sets stop-loss + target and **auto-cuts** on hit; everything is recorded to an isolated, auditable ledger.

### Locked decisions (from brainstorming)

| Axis | Decision | Consequence |
|---|---|---|
| Trading frequency | Minutes-to-hours (15m candles) | Latency irrelevant; no HFT, no Rust hot-path |
| Capital | Paper/research first; live later | Correctness > speed; kill-switch from day one |
| Infra | Single cheap VPS (~₹500–1,500/mo) | Co-locate Redis + Postgres; minimize processes |
| Language | Python-only | Async + Polars + uvloop; no Rust |
| Architecture | Hybrid supervised process groups | Isolate by failure domain, fuse the money-path |
| Markets | Crypto (Binance) now; Indian equity/F&O later | Abstract `MarketAdapter`; build Binance first |
| Sizing | Risk-based | qty derived from stop distance; fixed risk/trade |
| LLM authority | Full authority **within risk limits** | LLM controls *whether*; Risk Guard controls *how much* |
| Backtesting | Event-driven replay (same code) | Backtest = paper = live; no VectorBT divergence |
| AI scope | Core to the loop | Decision Agent is the take/reject/track brain |
| Build approach | True greenfield rewrite | New code; legacy is reference only |

---

## 2. Critique of the original IRON-v2 plan

The deliverable's first half: bottlenecks & shortcomings of the prior plan, given the locked scope.

### Premature optimization — removed from v2
1. **Rust hot-path / microsecond Order Gateway.** Unjustified for 15m strategies. A signal is valid for minutes; Binance's own REST/WS round-trip (10–100ms+) dwarfs any local micro-optimization, and a retail VPS cannot beat it without co-location. Pure build cost, zero benefit.
2. **Zero-copy / MessagePack / Apache Arrow IPC.** JSON over Redis moves thousands of 15m candles/sec trivially. Adds serialization complexity for no gain at this volume.
3. **Over-decomposition.** Rust feed + Rust gateway + Rust risk service + N strategy containers + Guru Ji on one cheap VPS is more IPC and ops than the box warrants.

### Real risks the original plan under-addressed — centered in v2
4. **No backtest/live parity.** Separate VectorBT backtests + separate live code = Sharpe becomes fiction the moment the two diverge. **v2 mandates one strategy implementation that runs in both modes** via injected clock/feed/execution.
5. **No data-integrity story.** No gap-filling, no warm-up (the legacy's known bug), no reconciliation of WS candles vs REST history. Silent gaps → wrong signals.
6. **Risk governance was a name, not a design.** Portfolio-level limits, daily-loss kill-switch, and order idempotency/dedup are what actually protect capital. v2 designs the Risk Guard as an independent fail-closed gate.
7. **Zero observability.** The legacy crashed *silently* on `BBL_20_2.0`. v2 makes heartbeats, metrics, and alerting first-class.

### Missing component the user's flow requires
8. **Position-lifecycle engine.** The original plan designed ingestion and signals in detail but had **no engine that owns an open trade, enforces SL/TP, and exits autonomously** — the *"trade register ho jaye jaha SL/target set kar saken aur auto cut ho jaye"* requirement. In systematic trading, exits make or lose the PnL. v2 makes the **Trade Engine + Position Monitor** a first-class component.

### Good instincts kept
9. **Redis Streams for signals/orders** — but for *durability/crash-recovery*, not speed. Pub/Sub stays for ephemeral ticks.
10. **Guru Ji async + timeout + deterministic fallback** — an LLM must never block the trade path.
11. **PnL isolation by `strategy_id`** — plus `trade_id` idempotency so replays/restarts never double-count.

---

## 3. Architecture — Component map & boundaries

Five supervised units (PM2/systemd). Split by **failure domain**: isolate things that fail messily and independently (feeds, strategies); fuse the critical money-path so there is never a network hop between "approved" and "stop registered".

```
[Crypto Feed]  [Indian Feed]      <- 1 process per market
      |  Redis Stream (candles) + Pub/Sub (fast prices)
      v
[Strategy Host]                   <- plugins = supervised async tasks
      |  Redis Stream (signals)
      v
+-- Core Engine (1 process, the money-path) --------+
|  Decision Agent (Guru Ji)  ->  Risk Guard         |
|     ->  Trade Engine (sets SL/TP)                  |
|     ->  Position Monitor (auto-cut)                |
+---------------------------+------------------------+
      v
[Postgres + TimescaleDB Ledger]

[Telegram Control/Notify]  + [Supervisor/Watchdog]  (cross-cutting)
```

### 3.1 Feed Service — one process per market (`feed-crypto`, `feed-india`)
- **Does:** owns the exchange/broker connection; normalizes raw data into a canonical `Candle` (identical schema across markets); warm-up backfill on new symbols; gap detection/fill; reconnect-with-resume; **session awareness** (crypto 24/7; India 09:15–15:30 IST + holidays).
- **In:** Binance WS (crypto) / Kite/Dhan WS (India). **Out:** `candles:{market}:{symbol}:{tf}` stream + `prices:{market}:{symbol}` fast stream + persist to `market_data`.
- **Why isolated:** a broker WS dropping or rate-limiting must never touch strategies or the money-path; crypto and Indian connection lifecycles differ completely.

### 3.2 Strategy Host — one process hosting all plugins (`strategy-host`)
- **Does:** loads plugins implementing a `Strategy` interface; each runs as a *supervised asyncio task* with its own rolling history. On each closed candle, a plugin may emit a `Signal`.
- **In:** candle streams (consumer group). **Out:** `signals` stream.
- **Isolation:** a plugin that throws is caught, logged, restarted — siblings keep running; persistent crashers are quarantined + alerted. A risky plugin can be promoted to its own process later with zero code change. Pure compute, no DB/exchange → trivially backtestable.

### 3.3 Core Engine — one process = the money-path (`core-engine`)
In-order, in-process sub-modules (atomic, no network between them):
- **Decision Agent (Guru Ji):** consumes `signals` → verdict `TAKE | REJECT | TRACK`.
- **Risk Guard:** independent fail-closed gate on `TAKE` only.
- **Trade Engine (OMS):** registers `Position` with entry + SL + target; broker-agnostic execution (paper now).
- **Position Monitor:** the auto-cut loop — SL/target/trailing/square-off, finalizes PnL.
- **Why one process:** decision→risk→execute→monitor is where partial failure = real loss (e.g., order placed but SL not registered). Atomic + heavily-tested + crash-recovers open positions from Postgres.

### 3.4 Control & Notify — Telegram (`control-bot`)
Commands (add/remove symbol, pause strategy, flip live↔paper, kill-switch, status/PnL) + notifications (taken/rejected, SL/target hit, process-down). Separate so user I/O never blocks the money-path. Talks to Core via a Redis command stream + reads the ledger.

### 3.5 Supervisor + Observability (cross-cutting)
PM2/systemd auto-restart; per-process heartbeat → Redis; watchdog alerts Telegram on stale beat. Structured logs + metrics. Never crash silently again.

---

## 4. Data contracts & stream topology

| Stream | Producer → Consumer | Type | Purpose |
|---|---|---|---|
| `candles:{market}:{symbol}:{tf}` | Feed → Strategy Host | Stream, `MAXLEN` capped | Closed candles for signal logic |
| `prices:{market}:{symbol}` | Feed → Position Monitor | Pub/Sub or capped Stream | **Fast price (1m/tick) for SL/TP watching** |
| `signals` | Strategy Host → Core | Durable Stream + consumer group | A restarting Core must not drop a signal |
| `commands` | Telegram → Core/Feeds | Durable Stream | Kill-switch / add-symbol must survive restart |
| `events` | Core → Telegram | Stream | Position opened, SL/target hit, kill-switch |

### Canonical messages (versioned with `schema_v`)

```
Candle  { schema_v, market, symbol, tf, open_time, close_time, o,h,l,c,v, closed:true, source }

Signal  { schema_v, signal_id(uuid), strategy_id, market, symbol, tf, side(long|short),
          confidence(0..1), suggested_entry, suggested_sl, suggested_tp,
          features{...}, candle_close_time, emitted_at }

Decision{ schema_v, decision_id, signal_id, verdict(TAKE|REJECT|TRACK),
          reason_code, llm_used(bool), llm_reasoning|null, sizing_hint, decided_at }

Position{ trade_id, signal_id, decision_id, strategy_id, market, symbol, side,
          mode(live|paper|shadow), entry_price, qty, stop_loss, target,
          trailing_cfg|null, status(open|closed), opened_at }

Exit    { trade_id, exit_price, exit_reason(sl|target|trailing|square_off|manual),
          pnl, closed_at }
```

### Delivery & correctness rules
- Durable streams use **consumer groups**; `XACK` only *after* the message is processed **and** persisted to Postgres → at-least-once delivery.
- **Idempotency is the golden thread:** `signal_id` dedups at Risk Guard; `trade_id` dedups at Trade Engine. Replays/restarts/redelivery can never double-enter a trade. (Exactly-once *effects* without exactly-once *delivery*.)
- On Core restart: load open positions from Postgres, resume monitoring, re-attach to consumer groups from last `XACK`.

### Two-granularity principle
Strategies **decide** on 15m candles; the Position Monitor **watches** on a finer stream (1m/tick). Checking the stop only on 15m closes lets a fast wick punch through it. Decision cadence and risk-monitoring cadence are independent design axes.

---

## 5. Money-path logic

### 5.1 Decision Agent (Guru Ji)
```
Signal -> [Deterministic gate]  (always runs)
            confidence floor · multi-strategy conviction · regime filter
            · opposing-signal conflict policy · already-open dedup
                | provisional verdict + reason_code
                v
          [LLM reasoning]  (async, hard timeout ~2s, borderline cases)
            input: signal + features + open portfolio
            timeout/error/invalid -> use provisional verdict (llm_used=false)
                v
          Verdict: TAKE -> Risk Guard | REJECT -> log+notify | TRACK -> shadow position
```
- **LLM authority = full within risk limits:** the LLM may upgrade TRACK→TAKE (not just downgrade), so `min_confidence` becomes *context the LLM weighs* rather than a hard floor. Safe because **Risk Guard is downstream and fail-closed** — the LLM controls *whether*, Risk Guard controls *how much*. Every LLM-driven TAKE logs `llm_used=true` + full reasoning for audit.
- **TRACK** → virtual/shadow position (monitored hypothetically, `shadow_positions` ledger, never sent to Risk Guard) — the paper-research feedback loop.

### 5.2 Risk Guard — fail-closed gate (TAKE only, in order)
```
1. Kill-switch ON?              -> reject all
2. Daily-loss breached?         -> trip kill-switch + reject
3. Portfolio exposure + trade   <= max?
4. Per-strategy capital cap     not exceeded?
5. Max concurrent positions     (global + per-symbol)?
6. Idempotency: signal_id seen? -> drop
7. SIZE (risk-based): qty s.t. (|entry - SL| * qty) <= max_risk_per_trade,
        and notional <= min(requested, max_allowed, remaining caps)
8. Market constraints: India lot/tick rounding; market open?
        -> approved Position(qty, SL, target)  OR  REJECT(risk, reason)
```
Any check failing → reject. Step 7 is **risk-based sizing**: every trade risks the same rupee amount regardless of price (fixes the legacy "always max size" bug).

### 5.3 Trade Engine + Position Monitor — auto-cut state machine
```
        PENDING_ENTRY --entry filled--> OPEN
                                          | on each fast price tick:
                                          |   SL hit?     (long px<=SL / short px>=SL)
                                          |   Target hit? (long px>=TP / short px<=TP)
                                          |   Trailing: ratchet SL favorably, never loosen
                                          |   Square-off? (india, t >= 15:20 IST)
                                          v first trigger wins
                                       EXITING --close confirmed--> CLOSED (PnL -> ledger)
```
- **Tick ordering in Core:** process exits for open positions *before* new entries — capital protection precedes deployment.
- **Honest gap handling:** if price gaps past the stop, exit at the actual available price and record real slippage — never pretend a fill exactly at SL. This is the difference between paper that predicts live and paper that flatters you.
- **Crash recovery:** on restart, reload PENDING/OPEN/EXITING from Postgres and resume; EXITING positions are reconciled (broker query live, re-evaluate paper).
- **Bracket integrity:** live mode prefers broker-native OCO/bracket so the stop survives a Core crash; paper manages SL/TP itself and relies on crash-recovery.

---

## 6. Cross-cutting concerns

### 6.1 Backtest/Live parity (#1 correctness principle)
Same strategy + Decision + Risk + Trade/Monitor code in both modes via dependency injection:
- **Clock** — injected, never `now()` directly (live = wall clock; backtest = simulated, advances per candle).
- **Feed** — live = Redis stream; backtest = TimescaleDB history replayed in order.
- **Execution** — live = broker; paper & backtest = same simulated fill model (honest slippage + fees).

Implies an **event-driven backtester** (replay through the real pipeline), *not* VectorBT — vectorized backtests are different code from the live path, which is how backtests come to lie. At 15m, replay speed is irrelevant; truthfulness isn't.

### 6.2 Ledger schema (Postgres + TimescaleDB)
- `market_data` — hypertable (time, market, symbol, tf, OHLCV) → queries, warm-up, backtest replay.
- `signals` → `decisions` → `positions` → `exits`, linked by `signal_id` / `trade_id` / `strategy_id`.
- `shadow_positions` — TRACK-mode virtual trades, isolated.
- `trade_events` — **append-only** audit log of every state transition; `positions` holds current mutable state.
- Strict PnL isolation per `strategy_id`; full audit trail signal→decision→order→exit.

### 6.3 Multi-market abstraction
One `MarketAdapter` interface: `connect / subscribe / normalize / session_info / place_order / get_positions`.
- `BinanceAdapter` (crypto, 24/7) — built first as reference.
- `Zerodha/DhanAdapter` (India: market hours, lot/tick sizes, square-off, F&O expiry) — later plug-in; interface defined now so it is never a rewrite.
- Session-awareness feeds Feed (no ticks when closed), Risk Guard (reject if closed), Monitor (square-off + overnight gaps).
- Canonical instrument model: symbol, market, lot_size, tick_size, asset_type (spot/futures/option), expiry?, multiplier.

### 6.4 Observability & supervision
Per-process **heartbeat** → Redis; watchdog alerts Telegram + triggers PM2 restart on stale beat. Structured JSON logs correlated by `trade_id`. Metrics: signals/min, verdicts, open positions, daily PnL, feed lag, LLM-timeout rate. Telegram alerts: process-down, kill-switch tripped, daily-loss nearing, feed gap, repeated strategy crash. (Prometheus/Grafana optional — start with logged metrics + `/status` to keep cost ~₹0.)

### 6.5 Failure modes (fail-closed throughout)
| Failure | Handling |
|---|---|
| Feed WS drop | reconnect+backoff; REST gap-fill on resume; alert if down |
| Malformed candle | validate at feed boundary; drop+log; never propagate NaN |
| Strategy throws | host restarts task; quarantine+alert after N crashes |
| LLM timeout | deterministic fallback; `llm_used=false` |
| Core crash | PM2 restart → reload open positions → resume monitor → reconcile EXITING |
| Postgres down | halt new entries (fail-closed); buffer; alert |
| Redis down | system halts — the one SPOF on a single VPS (accepted); mitigate with Redis AOF persistence |
| Duplicate delivery | idempotency keys → safe no-op |
| Order rejected (live) | mark position error; alert; no blind retry |

### 6.6 Testing
- **Unit:** indicator/sizing/verdict/SL-trigger math (pure functions).
- **Golden-path replay:** known historical window through the full pipeline; assert exact trades + PnL (regression guard).
- **Edge tests:** gap-through-stop, opposing signals, market-closed, daily-loss trip, duplicate signal, crash-recovery mid-trade.
- **Parity test:** same window through backtest and paper → assert identical decisions/exits. Proves parity, not assumes it.
- TDD discipline during implementation.

---

## 7. Phased roadmap

Vertical slices — each phase is an independently shippable, testable, end-to-end system.

| Phase | Deliverable |
|---|---|
| **0 — Foundations** | Repo skeleton, `config.yaml`, Postgres+Timescale schema, Redis on VPS, base interfaces (`Strategy`, `MarketAdapter`, `ExecutionAdapter`, `Clock`), message schemas, logging+heartbeat; PM2 boots empty pipeline |
| **1 — Data spine (crypto)** | `BinanceAdapter`: WS, normalize candles, warm-up backfill, gap-fill → Redis + `market_data` |
| **2 — Strategy + backtester** | `Strategy` plugin loader (supervised tasks); first strategy (MA crossover) emitting signals; event-driven backtester |
| **3 — Money-path core (paper)** | Decision Agent (rules + LLM stub), Risk Guard, Trade Engine (paper), Position Monitor (SL/TP/trailing/square-off), ledger; **parity test passing** |
| **4 — Control & observability** | Telegram bot, watchdog alerts, `/status`, `/pnl` |
| **5 — Guru Ji (LLM)** | LangGraph decision node, full-authority-within-limits, async+timeout+fallback, reasoning logged, TRACK→shadow loop, autonomous-backtest tool |
| **6 — India + live-ready** | `Zerodha/DhanAdapter` (sessions, lots, square-off, F&O), live `ExecutionAdapter` w/ broker brackets + reconciliation, graduated real-capital rollout |

Phases 0–4 → trustworthy paper lab. 5 → intelligence. 6 → live + Indian markets.

---

## 8. Cost

- Single cheap VPS ~₹500–1,500/mo; Postgres + Redis self-hosted on the same box = ₹0 extra.
- Only variable cost = Guru Ji's LLM calls. Borderline-only invocation + routing routine verdicts to **Haiku** and escalating to **Opus** only on conflicts ≈ **₹100–500/mo** at moderate volume.
- Net: a sub-₹2,000/mo institutional-style lab.

---

## 9. Out of scope / YAGNI

- Rust components; MessagePack/Arrow; zero-copy IPC.
- Sub-second / HFT execution; co-location.
- Multi-node / managed cloud / Kubernetes / HA clustering.
- VectorBT as the primary backtester.
- Pyramiding / position scaling (future config, not v1).
- Full Prometheus/Grafana stack (logged metrics + Telegram suffice initially).

---

## 10. Open questions (resolve during planning)

- Exact strategy set for v1 beyond MA crossover (RSI, squeeze)? — port math, rewrite code.
- Trailing-stop default: on/off and trail method (ATR vs fixed %)?
- LLM model routing thresholds (when Haiku vs Opus) and the borderline band definition.
- Indian broker choice (Zerodha Kite vs Dhan) — affects Phase 6 adapter.
- Paper fill model details: slippage assumption, fee schedule per market.
