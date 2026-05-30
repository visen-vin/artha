# Lightweight Paper+Live Trading App — Design & Spec

**Status:** Design approved (pre-implementation)  
**Date:** 2026-05-30  
**Complexity:** Medium (MVP with strategies + auto SL/TP)  
**Users:** 2 (personal use)  
**Markets:** Crypto (Binance) + Indian equity (Zerodha)

---

## 1. Vision & Scope

A **mobile-friendly web application** for personal paper and live trading. Users can:
- **Manually enter trades** (pick symbol, quantity, SL, TP, execute)
- **Run basic automated strategies** (MA crossover on 15m candles)
- **Auto stop-loss & take-profit** (triggers on price movement, closes position automatically)
- **Toggle paper ↔ live mode** (paper = simulated; live = real Binance/Zerodha orders)
- **See full trade history** (persisted across sessions)

**Key principle:** Lightweight monolithic backend. Single server handles feeds, strategies, trade execution, and API. SQLite for simplicity.

**Out of scope (Phase 2+):**
- Risk Guard / position caps / daily loss limits
- Backtesting engine
- Multiple strategies
- Telegram alerts
- Multi-user management (just 2 people, shared account mode)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  MOBILE-FRIENDLY WEB UI                  │
│         (React/Vue, responsive, no native app)          │
└────────────────┬──────────────────────────────────────┘
                 │ (REST API)
┌────────────────▼──────────────────────────────────────┐
│           PYTHON/NODE BACKEND (MONOLITHIC)             │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Feed Service                                     │ │
│  │  • Binance WS (crypto prices, candles)          │ │
│  │  • Zerodha Kite API (equity prices)             │ │
│  │  • Normalize → broadcast to UI + strategies     │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Strategy Engine                                  │ │
│  │  • MA 20/50 crossover (15m candles)            │ │
│  │  • Emits signals → UI + manual accept/reject   │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │ Trade Engine                                     │ │
│  │  • Open position (manual or strategy signal)    │ │
│  │  • Position Monitor: watch SL/TP on each tick  │ │
│  │  • Auto-close when triggered                    │ │
│  │  • Paper mode: simulated fills                 │ │
│  │  • Live mode: real Binance/Zerodha orders      │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
│  ┌──────────────────────────────────────────────────┐ │
│  │ REST API Server                                  │ │
│  │  • /positions → open trades                    │ │
│  │  • /history → closed trades + PnL              │ │
│  │  • /place-order → manual entry                 │ │
│  │  • /settings → toggle paper/live, auth tokens  │ │
│  └──────────────────────────────────────────────────┘ │
│                                                         │
└────────────────┬──────────────────────────────────────┘
                 │
┌────────────────▼──────────────────────────────────────┐
│              SQLITE DATABASE                           │
│  (positions, trades, signals, candle history)         │
└────────────────────────────────────────────────────────┘

External APIs (free):
  • Binance REST / WebSocket (price feeds, orders)
  • Zerodha Kite OAuth + API (equity prices, orders)
```

---

## 3. Components

### 3.1 Feed Service
**Responsibility:** Ingest live prices and candles, normalize, broadcast.

**Data sources:**
- **Binance:** WebSocket (USDT pairs) for real-time ticks; REST for historical candles (backfill on startup)
- **Zerodha Kite:** REST API (no native WS) polling every 30s for equity/F&O prices

**Inputs:** None (connects outbound to exchanges)  
**Outputs:** 
- Real-time price ticks → Position Monitor (for SL/TP checking)
- Closed 15m candles → Strategy Engine (for signals)
- Live prices → UI broadcast (WebSocket or polling fallback)

**Logic:**
```python
# Pseudo
while running:
  binance_prices = await fetch_binance_ws()      # ~100ms latency
  zerodha_prices = await fetch_zerodha_api()     # ~500ms, poll every 30s
  
  # Normalize to canonical format
  prices = normalize(binance_prices + zerodha_prices)
  
  # Broadcast to all subscribers
  await broadcast_to_ui(prices)
  await broadcast_to_position_monitor(prices)
  
  # On 15m candle close
  if candle_closed():
    candles = aggregate_to_15m(prices)
    await broadcast_to_strategy_engine(candles)
```

### 3.2 Strategy Engine
**Responsibility:** Run strategy logic, emit signals.

**Inputs:** Closed 15m candles from Feed Service  
**Outputs:** Signals → UI + Trade Engine

**Initial strategy: MA 20/50 Crossover**
```
For each symbol on each 15m close:
  ma_20 = average(close[last 20 candles])
  ma_50 = average(close[last 50 candles])
  
  if ma_20 > ma_50 and was_not_bullish:
    → emit LONG signal (confidence = 0.75)
  
  if ma_20 < ma_50 and was_not_bearish:
    → emit SHORT signal (confidence = 0.75)
  
  else if no crossover:
    → emit TRACK signal (log hypothesis, don't open trade)
```

**Signal format:**
```json
{
  "signal_id": "uuid",
  "strategy": "ma_crossover",
  "symbol": "BTCUSDT",
  "side": "long",
  "confidence": 0.75,
  "entry_hint": null,
  "sl_hint": null,
  "tp_hint": null,
  "emitted_at": "2026-05-30T15:30:00Z",
  "candle_close_time": "2026-05-30T15:30:00Z"
}
```

### 3.3 Trade Engine + Position Monitor
**Responsibility:** Manage open trades, execute SL/TP, close positions.

**Inputs:**
- Manual trade requests (from UI)
- Strategy signals (auto-accept or manual accept)
- Price ticks (for SL/TP checking)

**Outputs:**
- Position opened event → UI + DB
- Position closed event (SL/TP hit) → UI + DB
- PnL calculated

**Position state machine:**
```
PENDING_ENTRY
  ├─ (user clicks manual trade)
  └─→ OPEN
      ├─ (each price tick)
      │  ├─ SL hit? → CLOSED (loss)
      │  ├─ TP hit? → CLOSED (profit)
      │  └─ still open → OPEN
      │
      └─→ (user clicks close button) → CLOSED (manual)
```

**SL/TP check logic (runs on every price tick):**
```python
def monitor_positions(positions, current_price):
  for position in positions:
    if position.status != "OPEN":
      continue
    
    symbol = position.symbol
    if current_price[symbol] == None:
      continue  # no price yet
    
    price = current_price[symbol]
    
    # Check SL
    if position.side == "long" and price <= position.sl:
      close_position(position, price, "SL")
    elif position.side == "short" and price >= position.sl:
      close_position(position, price, "SL")
    
    # Check TP
    if position.side == "long" and price >= position.tp:
      close_position(position, price, "TP")
    elif position.side == "short" and price <= position.tp:
      close_position(position, price, "TP")
```

**Paper vs Live execution:**
```python
def open_position(symbol, side, qty, entry, sl, tp, mode="paper"):
  position = Position(...)
  
  if mode == "paper":
    # Simulated: assume fill at entry_price
    position.entry_price = entry
    position.status = "OPEN"
  else:
    # Live: place real order via Binance/Zerodha
    order = await place_market_order(symbol, side, qty, entry)
    if order.status == "filled":
      position.entry_price = order.avg_price
      position.status = "OPEN"
    else:
      position.status = "PENDING_ENTRY"  # waiting for fill
  
  db.save(position)
  return position
```

### 3.4 REST API Server
**Framework:** FastAPI (Python) or Express (Node)

**Endpoints:**

| Endpoint | Method | Purpose | Body |
|---|---|---|---|
| `/positions` | GET | List open trades | — |
| `/history` | GET | Closed trades (last 30 days) | `?limit=50&offset=0` |
| `/place-order` | POST | Manual trade entry | `{symbol, side, qty, entry, sl, tp}` |
| `/close-position` | POST | Manual close | `{position_id}` |
| `/settings` | GET/POST | Paper/live toggle, API keys | `{mode, binance_key?, zerodha_token?}` |
| `/prices` | GET | Current prices (for UI) | `?symbols=BTC,AAPL` |
| `/signals` | GET | Recent signals (for UI) | `?limit=10` |
| `/auth/zerodha` | GET | Zerodha OAuth redirect | — |
| `/auth/zerodha/callback` | GET | OAuth callback, store token | `?code=...` |

---

## 4. Frontend

**Tech:** React or Vue (choice doesn't matter for this scope)  
**Responsive:** Mobile-first (works on phone, tablet, desktop)

**Key screens:**

**1. Dashboard**
- Live price ticker (top): BTC/USDT, AAPL, TSLA, etc.
- Open positions panel (left): entry, SL, TP, current PnL, % return
- Manual trade form (center): symbol dropdown, side (long/short), qty, entry, SL, TP, big "EXECUTE" button
- Signals log (right, optional): "MA signal: BTC long 0.75" with accept/reject buttons

**2. History**
- Table: symbol, entry, exit, PnL, exit_reason (SL/TP/manual), timestamp
- Filter: last 7 days, last 30 days, all

**3. Settings**
- Paper / Live toggle (big switch, warning on live mode)
- Binance API key input (masked)
- Zerodha login button ("Connect with Zerodha")
- Disconnect buttons

**4. Alerts (optional for MVP)**
- Toast notifications: "Position opened: BTC long @ ₹2,500,000"
- Toast notifications: "SL hit: -₹10,000"

---

## 5. Data Models

### Database Schema (SQLite)

**`positions` table**
```sql
CREATE TABLE positions (
  id TEXT PRIMARY KEY,
  signal_id TEXT,                    -- NULL if manual, else strategy signal
  symbol TEXT NOT NULL,              -- "BTCUSDT", "AAPL", "INFY"
  market TEXT NOT NULL,              -- "crypto", "indian_equity"
  side TEXT NOT NULL,                -- "long" or "short"
  qty REAL NOT NULL,
  entry_price REAL NOT NULL,
  sl REAL NOT NULL,
  tp REAL NOT NULL,
  status TEXT NOT NULL,              -- "OPEN", "CLOSED"
  mode TEXT NOT NULL,                -- "paper", "live"
  opened_at TIMESTAMP NOT NULL,
  closed_at TIMESTAMP,
  exit_price REAL,
  exit_reason TEXT,                  -- "SL", "TP", "manual", null if open
  pnl REAL                           -- only if closed
);
```

**`signals` table**
```sql
CREATE TABLE signals (
  signal_id TEXT PRIMARY KEY,
  strategy TEXT NOT NULL,            -- "ma_crossover"
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,                -- "long", "short", "track"
  confidence REAL,                   -- 0.0 to 1.0
  emitted_at TIMESTAMP NOT NULL,
  candle_close_time TIMESTAMP
);
```

**`candles` table** (optional, for backtest + strategy rolling window)
```sql
CREATE TABLE candles (
  id INTEGER PRIMARY KEY,
  symbol TEXT NOT NULL,
  market TEXT NOT NULL,
  timeframe TEXT NOT NULL,           -- "15m", "1h", etc.
  open_time TIMESTAMP NOT NULL,
  close_time TIMESTAMP NOT NULL,
  o REAL, h REAL, l REAL, c REAL, v REAL
);
CREATE INDEX idx_candles ON candles(symbol, market, timeframe, close_time);
```

---

## 6. Key Features & Behavior

### Feature 1: Manual Trading
1. User enters symbol (dropdown: BTCUSDT, AAPL, INFY-EQ, etc.)
2. User selects side: long or short
3. User enters: qty, entry price, SL, TP
4. Click "EXECUTE"
5. Backend checks mode:
   - **Paper:** immediately simulates fill @ entry price, opens position
   - **Live:** places market order via Binance/Zerodha API, waits for fill confirmation
6. Position appears in "Open Positions" panel
7. UI updates in real-time as prices change (calculated PnL)

### Feature 2: Auto SL/TP
1. Position is open
2. Feed Service streams price ticks
3. Position Monitor checks each tick:
   - **If price ≤ SL (long):** close at SL price, record loss
   - **If price ≥ TP (long):** close at TP price, record profit
4. UI broadcasts: "Position closed: TP hit, +₹5,000"
5. Position moved to "History" tab

### Feature 3: Strategy Signals
1. Strategy Engine runs on closed 15m candles
2. MA20 > MA50 → emits LONG signal (confidence 0.75)
3. Signal appears in UI: "MA Crossover: BTC long (confidence 0.75) — [Accept] [Reject]"
4. User clicks "Accept" → same as manual trade (opens position with signal link)
5. User clicks "Reject" → signal logged (no position)
6. No-action (30s timeout) → signal auto-expires (not opened)

### Feature 4: Paper vs Live Mode
1. **Paper mode (default):**
   - All orders simulated
   - Fills at entry price immediately
   - No real money at risk
   - Useful for learning / testing strategies

2. **Live mode (with warning):**
   - Real Binance / Zerodha orders
   - Real PnL on actual capital
   - Requires API keys authenticated
   - Warning modal on first toggle: "Live mode ENABLED. Real orders will execute."

### Feature 5: History & PnL Tracking
1. All closed trades persisted to DB
2. History tab shows: entry, exit, reason (SL/TP/manual), PnL, %return
3. Sortable by symbol, date, PnL
4. Filter: last 7 days, 30 days, all

---

## 7. External Integrations

### Binance API (Free)

**WebSocket (live prices + candles):**
```
wss://stream.binance.com:9443/ws
  • Candle stream: "BTCUSDT@klines_15m" → closed 15m candles
  • Tick stream: "BTCUSDT@trade" → individual trades (fast prices)
```

**REST API (orders, account info):**
```
POST https://api.binance.com/api/v3/order
  • Place market order: side, symbol, quantity, timestamp, signature
  • Live mode only
```

**Auth:** API key + secret (user stores in app settings, no backend storage)

### Zerodha Kite API (Free with account)

**OAuth flow:**
```
1. User clicks "Connect Zerodha"
2. App redirects: https://kite.zerodha.com/connect/login?api_key=...
3. User logs in to Zerodha
4. Zerodha redirects back: /auth/zerodha/callback?code=...
5. Backend exchanges code for access_token
6. Token stored locally (expiry: ~24 hours, manual refresh)
```

**REST API (prices, orders):**
```
GET https://api.kite.zerodha.com/portfolio/positions
GET https://api.kite.zerodha.com/quote/?i=NSE:INFY
POST https://api.kite.zerodha.com/orders/regular (place order)
```

**Auth:** Bearer token from OAuth

---

## 8. Error Handling

| Failure | Handling |
|---|---|
| **Binance WS drops** | Reconnect with exponential backoff; UI shows "Offline" |
| **Zerodha API timeout** | Fall back to cached price; alert user |
| **Order rejected (live)** | Log error; show user: "Order rejected: [reason]"; no retry |
| **SL/TP exact match miss** | No exact fills in paper mode; use next available price |
| **Database write fails** | Transaction rolls back; UI error toast |
| **Strategy throws** | Catch exception; log; skip signal; continue |
| **Auth token expired** | Refresh token; if refresh fails, show "Reconnect Zerodha" prompt |

---

## 9. Testing Strategy

### Unit Tests
- `test_ma_strategy.py`: test MA 20/50 crossover logic on sample candles
- `test_position_monitor.py`: test SL/TP trigger logic (long/short, boundary cases)
- `test_paper_fill.py`: test paper fill simulation logic
- `test_pnl_calculation.py`: test PnL math (long entry/exit, short entry/exit)

### Integration Tests
- `test_trade_flow_manual.py`: manual trade → open → SL hit → closed
- `test_trade_flow_strategy.py`: signal → auto accept → open → TP hit → closed
- `test_mode_toggle.py`: paper mode → live mode → back to paper (orders differ)

### Manual Smoke Tests
- UI dashboard loads and shows live prices (Binance + Zerodha)
- Manual trade: can open, can see in positions panel, SL/TP updates on price movement
- Strategy: MA signal appears, can accept/reject
- Paper mode: trades simulate correctly, PnL calculates
- Live mode: (on test account) real orders place and execute
- History: closed trades appear with correct PnL
- Settings: can toggle paper/live, can paste Binance key, can auth Zerodha

---

## 10. Phased Roadmap

| Phase | Deliverable | Timeline |
|---|---|---|
| **Phase 1 — Foundations** | Repo skeleton, database schema, Feed Service (Binance only), REST API scaffold | 2-3 days |
| **Phase 2 — Manual Trading** | Trade Engine (paper mode), SL/TP monitor, basic UI (mobile), manual order form | 3-4 days |
| **Phase 3 — Strategy** | Strategy Engine (MA crossover), signals in UI, signal accept/reject logic | 2-3 days |
| **Phase 4 — Zerodha + Persistence** | Zerodha OAuth, Zerodha price feed, history tab, trades persisted | 2-3 days |
| **Phase 5 — Live Mode** | Live order placement (Binance + Zerodha), paper/live toggle, live warnings | 2-3 days |
| **Phase 6 — Polish & Deploy** | UI polish, mobile responsiveness, error handling, deployment to VPS | 2-3 days |

**Total estimate: 2-3 weeks** for a working, sharable paper+live trading app.

---

## 11. Cost & Infrastructure

**APIs:** ₹0 (all free)
- Binance: free
- Zerodha: free (included with account)

**Hosting (optional):**
- **Option A (local):** Run on your laptop, access from mobile via local IP or ngrok tunneling → ₹0
- **Option B (VPS):** Cheap VPS (₹500–1,500/mo) running 24/7 for continuous feed + strategies
- **Option C (hybrid):** Run locally when trading, stop when not needed → ₹0

**Database:** ₹0 (SQLite on same server)

**Total recurring cost: ₹0–1,500/mo** (depends on hosting choice)

---

## 12. Out of Scope (Phase 2+)

- Risk Guard (daily loss limit, position caps, portfolio concentration)
- Backtesting engine
- Multiple strategies (beyond MA crossover)
- Telegram alerts / Discord webhooks
- Multi-strategy portfolio tracking
- Advanced order types (limit orders, trailing stops)
- Options / derivatives support
- Tax reporting
- API rate limit handling (assume sufficient for 2 users)

---

## 13. Success Criteria

✅ You and your brother can:
- See live crypto + equity prices
- Manually open/close trades with SL/TP
- Let MA crossover auto-generate signals, accept/reject them
- Toggle paper ↔ live mode
- See full trade history (PnL, exit reason)
- Have zero data loss (trades persist across sessions)

✅ All errors handled gracefully (no crashes)

✅ Mobile-friendly UI works on phone, tablet, desktop

✅ Paper mode is accurate (reflects real trading logic)

---

**Next step:** Write implementation plan (Phase 1–6 detailed breakdown with file structure, dependencies, API design).
