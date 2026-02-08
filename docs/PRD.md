# Product Requirement Document: Autonomous Options Day Trading Agent

## 1. Overview

An AI-powered autonomous agent that day-trades stock options on the Indian F&O market (NSE). The agent operates as an expert trader — analyzing markets pre-open, selecting high-conviction stocks, entering and managing option trades, monitoring positions in real-time, and squaring off before market close. It maintains a trade diary for continuous learning.

**Codename:** Options Day Trader Agent (ODTA)

---

## 2. Goals & Non-Goals

### Goals
- Autonomously identify 2-5 high-potential F&O stocks each trading day
- Execute directional option trades (buy calls/puts) with defined risk
- Monitor positions every 1-5 minutes and take corrective actions
- Enforce strict risk management: max daily loss of Rs 5,000
- Square off all positions by 3:00 PM IST
- Maintain a trade diary with daily summaries and learnings
- Operate without human intervention once started

### Non-Goals (Phase 1)
- Multi-leg strategies (spreads, straddles, iron condors) — future phases
- Overnight/positional trades
- Index option trading (Nifty/BankNifty) — can be added later
- Automated fund management or withdrawal

---

## 3. Architecture

### 3.1 High-Level Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    GOOGLE ADK AGENT TREE                         │
│                                                                  │
│  root_agent (SequentialAgent: "daily_session")                   │
│  │                                                               │
│  ├── pre_market_agent (SequentialAgent)                          │
│  │     ├── diary_reader (LlmAgent)                               │
│  │     ├── market_scanner (LlmAgent)  ──→ SQL, Indicators,      │
│  │     │                                   Market Sentiment      │
│  │     ├── news_agent (LlmAgent)      ──→ Google Search          │
│  │     └── watchlist_finalizer (LlmAgent)                        │
│  │                                                               │
│  ├── trading_loop (LoopAgent)                                    │
│  │     ├── trader_agent (LlmAgent)    ──→ ALL tools (MCP + native│
│  │     │     before_tool_callback: risk_manager                  │
│  │     └── loop_controller (BaseAgent) ──→ time/P&L check, sleep │
│  │                                                               │
│  └── eod_agent (LlmAgent)            ──→ Diary write, summary   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                        TOOLS                                     │
│                                                                  │
│  MCP Tools (Angel One)          Native Python Tools              │
│  ┌──────────────────┐          ┌──────────────────────┐         │
│  │ place_order       │          │ query_database (SQL)  │         │
│  │ get_positions     │          │ calculate_greeks      │         │
│  │ get_ltp_data      │          │ calculate_indicators  │         │
│  │ get_candle_data   │          │ market_sentiment      │         │
│  │ get_option_greek  │          │ trade_diary r/w       │         │
│  │ search_scrip      │          │ decision_logger       │         │
│  │ get_order_book    │          │ paper_tracker         │         │
│  │ modify/cancel     │          │ chart_generator (P2)  │         │
│  └──────────────────┘          └──────────────────────┘         │
│                                                                  │
│  Risk Manager (before_tool_callback — NOT an LLM tool)           │
└──────────────────────────────────────────────────────────────────┘
         │                                    │
    ┌────▼────┐                          ┌────▼────┐
    │ Database │                          │Angel One│
    │ (DuckDB) │                          │MCP Server│
    │          │                          │(submodule)│
    └─────────┘                          └─────────┘
```

### 3.2 Orchestration Framework: Google ADK

The agent is built on [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/), which provides:

- **Agentic loop** — reasoning-action-observation cycle with automatic tool calling
- **Agent composition** — `SequentialAgent`, `LoopAgent`, `ParallelAgent` for orchestration (zero LLM calls)
- **Native MCP support** — `McpToolset` connects directly to Angel One MCP server
- **Multi-LLM** — model-agnostic. Switch LLM by changing the `model` parameter (Gemini, Claude, Ollama, vLLM, LiteLLM)
- **Session/state management** — built-in `SessionService` with state dict accessible by all agents and tools
- **`before_tool_callback`** — perfect for risk manager middleware
- **Built-in dev UI** — `adk web` for interactive testing and debugging
- **Dynamic instructions** — instruction can be a function that injects live state (P&L, phase, watchlist)

**No custom LLM abstraction layer needed.** ADK handles multi-LLM natively — switching from Gemini to Claude is a config change (`model` parameter), not a code change.

**Initial LLM:** Gemini 2.0 Flash
**Supported:** Claude, OpenAI, Ollama, vLLM, LiteLLM

### 3.3 Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Orchestrator | Google ADK (`google-adk`) |
| Database | DuckDB |
| Broker API | Angel One MCP Server (git submodule, connected via `McpToolset`) |
| LLM | Gemini 2.0 Flash (swappable via ADK) |
| News/Search | Gemini Google Search Grounding (native tool, no external API) |
| Charts | mplfinance + Gemini Vision (Phase 2) |
| Technical Indicators | pandas-ta |
| Frontend | Next.js (dashboard + workflow visualizer) |
| Dev UI | `adk web` (built-in ADK dev interface) |
| Scheduling | Simple sleep loop (local). Cloud scheduling in future phase. |

---

## 4. Agent Workflow

### 4.1 Daily Lifecycle

```
08:45  ─── Agent Starts ───────────────────────────────────
  │
  ├── Phase 1: PRE-MARKET ANALYSIS (08:45 - 09:10)
  │     ├── Read trade diary for past learnings
  │     ├── Check ban list → exclude banned securities
  │     ├── Assess market regime (Nifty trend, BankNifty for financials)
  │     ├── Analyze sector-level sentiment & momentum
  │     ├── Query OHLCV DB → scan all F&O stocks
  │     ├── Apply stock selection criteria (see 4.2)
  │     ├── Fetch news for shortlisted stocks
  │     ├── Generate benchmark chart (Nifty) + stock charts
  │     ├── Analyze charts via LLM vision (with index overlay)
  │     ├── Calculate technical indicators
  │     └── Output: 2-5 watchlist stocks with directional bias
  │
09:15  ─── Market Opens ───────────────────────────────────
  │
  ├── Phase 2: TRADE PLANNING (09:15 - 09:30)
  │     ├── Observe opening price action (15 min)
  │     ├── Fetch option chains for watchlist stocks
  │     ├── Calculate Greeks & IV for relevant strikes
  │     ├── Validate directional bias with live data
  │     ├── Consider expiry proximity (avoid near-expiry theta decay)
  │     ├── Determine entry strike, SL, target
  │     └── Output: Trade plan (or "continue scanning")
  │
  ├── Phase 3: TRADE EXECUTION & OPPORTUNITY SCANNING (09:30+)
  │     ├── If trade plan exists → execute via Angel One API
  │     ├── Confirm order execution & log entry in trade diary
  │     ├── If NO trade plan → continue scanning for setups
  │     ├── Agent remains active all day looking for opportunities
  │     └── New setups can emerge at any time until 2:45 PM
  │
  ├── Phase 4: POSITION MONITORING (ongoing, every 1-5 min)
  │     ├── Check current P&L
  │     ├── Check if daily max loss (5k) is breached
  │     ├── Re-evaluate chart & indicators (intraday candles from broker)
  │     ├── Decide: HOLD / TRAIL SL / EXIT / ADD
  │     ├── If no position & opportunity arises: evaluate & enter
  │     └── If SL hit or target reached: exit, log, resume scanning
  │
15:00  ─── Square Off ─────────────────────────────────────
  │
  ├── Phase 5: END OF DAY (15:00 - 15:15)
  │     ├── Square off ALL open positions
  │     ├── Fetch final P&L from broker
  │     ├── Generate daily summary
  │     ├── Update trade diary with learnings
  │     └── Agent shuts down
```

### 4.2 Stock Selection Criteria

The agent follows a top-down approach — market first, then sector, then stock:

1. **Exclude banned securities** — query ban list table first
2. **Assess market regime** — classify Nifty (and BankNifty) as bullish/bearish/sideways using the Market Sentiment tool. This sets the directional context.
3. **Identify strong sectors** — find sectors with momentum aligned with (or against) the market trend
4. **Volume spike** — recent volume significantly above average (agent decides threshold)
5. **Price near key levels** — support/resistance, moving averages, 52w high/low
6. **Range expansion** — stocks showing wider-than-normal daily range
7. **News catalyst** — stocks with recent news (earnings, results, events)
8. **Sufficient option liquidity** — tight bid-ask spreads in option chain (checked via broker API)

The agent dynamically writes SQL queries to filter and rank stocks. Goal: narrow 200+ F&O stocks down to 2-5 actionable names. All filtering thresholds (volume multiplier, lookback period, etc.) are decided by the agent based on current market conditions.

---

## 5. Tool Specifications

### 5.1 SQL Agent (Database Tool)

**Purpose:** Query OHLCV data, ban list, and trade diary from the database.

```
Tool: query_database
Input: { "sql": "SELECT ...", "explanation": "why this query" }
Output: { "columns": [...], "rows": [...], "row_count": N }
```

**Database:** `data/stocks.duckdb` (existing, symlinked or referenced from external location)

**Existing tables:**
- `daily_ohlcv` — columns: symbol, date, series, open, high, low, close, prev_close, volume, value, vwap, trades, delivery_volume, delivery_pct
- `fno_stocks` — columns: symbol, company_name, lot_size, last_updated (lot_size needs population)
- `index_ohlcv` — columns: index_name, date, open, high, close, low (Nifty 50; BankNifty to be added)

**Tables to create:**
- `ban_list` — securities currently in F&O ban period (symbol, ban_date)
- `trade_diary` — past trades and learnings (see 5.9)
- `decision_log` — agent decision trail (see Section 13)
- `paper_positions` — paper trading position tracking

**Constraints:**
- Read-only access to market data tables
- Write access only to `trade_diary` table
- Query timeout: 5 seconds

### 5.2 Broker API (Angel One — Full MCP/API Exposure)

**Purpose:** Fetch live/intraday data and execute trades. All Angel One SmartAPI endpoints are exposed as tools.

**Market Data Tools:**
```
Tool: get_option_chain
Input: { "symbol": "RELIANCE", "expiry": "2025-01-30" }
Output: { option chain data with strikes, premiums, OI, volume }

Tool: get_ltp
Input: { "symbol": "RELIANCE", "exchange": "NSE" }
Output: { "ltp": 2450.50 }

Tool: get_candle_data
Input: { "symbol": "RELIANCE", "exchange": "NSE", "interval": "FIVE_MINUTE", "from": "2025-01-28 09:15", "to": "2025-01-28 15:30" }
Output: { OHLCV candle data for intraday timeframes }

Tool: get_market_depth
Input: { "symbol": "RELIANCE", "exchange": "NSE" }
Output: { bid/ask depth, best 5 levels }
```

**Order & Position Tools:**
```
Tool: place_order
Input: { "symbol": "RELIANCE25JAN2500CE", "qty": 250, "order_type": "LIMIT", "price": 45.50, "transaction_type": "BUY" }
Output: { "order_id": "...", "status": "PLACED" }

Tool: modify_order
Input: { "order_id": "...", "price": 46.00 }
Output: { "status": "MODIFIED" }

Tool: cancel_order
Input: { "order_id": "..." }
Output: { "status": "CANCELLED" }

Tool: get_order_status
Input: { "order_id": "..." }
Output: { order details and fill status }

Tool: get_positions
Input: {}
Output: { current open positions with P&L }

Tool: get_order_book
Input: {}
Output: { all orders placed today with statuses }
```

**Note:** Any additional Angel One SmartAPI endpoint can be exposed as a tool. The broker module wraps the full API surface.

### 5.3 Greeks & IV Calculator

**Purpose:** Calculate option Greeks and implied volatility.

```
Tool: calculate_greeks
Input: { "spot_price": 2450, "strike": 2500, "expiry_days": 5, "premium": 45, "option_type": "CE", "risk_free_rate": 0.07 }
Output: { "iv": 0.23, "delta": 0.45, "gamma": 0.008, "theta": -12.5, "vega": 3.2 }
```

### 5.4 News Tool (Gemini Google Search Grounding)

**Purpose:** Search for real-time stock news, market events, and sector developments.

**Implementation:** Uses Gemini's built-in `google_search` grounding tool — NOT a separate news API. When the agent needs news, Gemini automatically searches Google and returns grounded results with source citations.

**ADK limitation:** `google_search` cannot coexist with other tools in the same `LlmAgent`. Therefore, news search runs in a **dedicated `news_agent`** (isolated LlmAgent with only `google_search` tool).

**Usage:**
- **Pre-market:** `news_agent` runs as part of the pre-market pipeline. Searches for earnings, corporate actions, sector news, and analyst calls for shortlisted stocks. Output saved to `state["news_analysis"]`.
- **During trading:** Wrapped as an `AgentTool` so the `trader_agent` can invoke it mid-day for breaking news on sudden price moves.

```python
# Pre-market: dedicated sub-agent
news_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="news_analyst",
    instruction="Search for recent news about {watchlist_candidates}...",
    tools=[google_search],
    output_key="news_analysis",
)

# Mid-day: wrapped as a callable tool for trader_agent
news_tool = AgentTool(agent=news_agent)
```

**Output:** Structured summary per stock with sentiment classification (bullish/bearish/neutral) and source citations.

### 5.5 Market Sentiment & Regime Tool

**Purpose:** Assess overall market direction, sector trends, and classify the trading regime. This is critical context before any stock-level analysis.

```
Tool: get_market_regime
Input: { "index": "NIFTY" }  # or "BANKNIFTY"
Output: {
  "trend": "bullish",           # bullish / bearish / sideways
  "regime": "trending",         # trending / ranging / volatile
  "key_levels": { "support": 21800, "resistance": 22200 },
  "sector_heatmap": { "IT": "+1.2%", "Banking": "-0.5%", "Auto": "+0.8%", ... },
  "fii_dii_flow": { "fii": -1200, "dii": +800 },   # crores, if available
  "vix": 14.5
}

Tool: get_sector_sentiment
Input: { "sector": "Banking" }
Output: {
  "top_gainers": ["HDFCBANK +1.5%", "ICICIBANK +1.2%"],
  "top_losers": ["PNB -0.8%"],
  "sector_trend": "mildly bullish",
  "relevant_index": "BANKNIFTY"
}
```

**Usage in workflow:**
- Pre-market: Classify market regime to set the tone for stock selection
- During trading: If taking a directional bet on a financial stock, check BankNifty trend. Don't go long on a banking stock if BankNifty is in a clear downtrend.
- Chart analysis: Benchmark index chart (Nifty/BankNifty) is generated alongside the stock chart so the agent can visually compare relative strength.

### 5.6 Chart Generator + Vision

**Purpose:** Generate candlestick charts and interpret them via LLM vision.

```
Tool: generate_and_analyze_chart
Input: { "symbol": "RELIANCE", "period": "3M", "indicators": ["SMA_20", "SMA_50", "RSI", "VWAP"] }
Output: { "chart_image_path": "/tmp/chart.png", "analysis": "LLM interpretation of the chart..." }
```

The chart is generated as a PNG, then passed to the LLM's vision capability for interpretation (support/resistance levels, patterns, trend direction). When analyzing a stock, the benchmark index chart (Nifty, or BankNifty for financial stocks) is included alongside for relative strength comparison.

### 5.7 Technical Indicators

**Purpose:** Calculate any technical indicator on-the-fly.

```
Tool: calculate_indicator
Input: { "symbol": "RELIANCE", "indicator": "RSI", "params": { "period": 14 }, "timeframe": "daily" }
Output: { "values": [{ "date": "2025-01-28", "RSI": 65.4 }, ...] }
```

Supported indicators: RSI, MACD, Bollinger Bands, SMA, EMA, VWAP, ATR, SuperTrend, ADX, Stochastic, OBV, and any indicator supported by pandas-ta.

### 5.8 Risk Manager (Internal Module, Not a Tool)

This is an internal guardrail, not an LLM tool. It runs as middleware before every order. Only absolute safety limits are hardcoded here — everything else is left to the agent's judgment.

**Hardcoded rules (not overridable by LLM):**

| Rule | Value | Rationale |
|------|-------|-----------|
| Max daily loss | Rs 5,000 | Absolute capital protection |
| Max open positions | 2 | Prevent over-exposure |
| Square off time | 3:00 PM IST | No overnight risk |
| No trading in banned securities | Enforced | Regulatory compliance |
| Order size validation | Lot size must match F&O lot | Prevent invalid orders |

If daily loss limit is hit → all positions are squared off immediately and no new trades are allowed.

**Agent-decided parameters (NOT hardcoded):**
The following are intentionally left to the agent's judgment rather than being configured externally. The agent should reason about these based on market conditions, volatility, and its own assessment:

- When to enter "defensive mode" (reduce risk appetite)
- Per-trade stop-loss levels and alert thresholds
- Which order types to use (buy/sell) — agent evolves as strategies expand
- Minimum volume thresholds for stock selection
- Lookback period for analysis
- Position sizing within the lot constraint

The philosophy: **configure guardrails, not trading logic.** The agent should think like a trader, not follow a rigid rulebook.

### 5.9 Trade Diary

**Purpose:** Persistent memory for the agent across trading days.

**Schema:**
```sql
CREATE TABLE trade_diary (
    id INTEGER PRIMARY KEY,
    trade_date DATE,
    symbol VARCHAR,
    option_symbol VARCHAR,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    entry_price DECIMAL,
    exit_price DECIMAL,
    quantity INTEGER,
    direction VARCHAR,        -- BUY_CE / BUY_PE
    pnl DECIMAL,
    entry_rationale TEXT,     -- why the agent entered
    exit_rationale TEXT,      -- why the agent exited
    market_conditions TEXT,   -- agent's view of market that day
    learnings TEXT,           -- what the agent learned from this trade
    mistakes TEXT,            -- what went wrong (self-critique)
    daily_summary TEXT,       -- end-of-day summary (one per day)
    tags VARCHAR              -- e.g., "breakout,momentum,news-driven"
);
```

**Read at start of day:** Agent reviews last 10-20 trades for patterns, recurring mistakes, and successful setups.

**Write at end of day:** Agent fills in learnings, mistakes, and daily summary with self-reflection.

### 5.10 Trade Diary Reader (Tool for Pre-Market)

```
Tool: read_trade_diary
Input: { "last_n_trades": 15, "include_daily_summaries": true }
Output: {
  "trades": [...],
  "recurring_patterns": "Agent's past observations...",
  "common_mistakes": ["entering against index trend", "holding too long in afternoon"],
  "best_setups": ["momentum breakout with volume", "gap-up continuation"]
}
```

This is a read-only tool the agent uses during pre-market to prime its decision-making with past experience.

---

## 6. Orchestrator Agent Design (Google ADK)

### 6.1 Agent Tree Architecture

ADK replaces the custom `while` loop with composable agent primitives:

- **`SequentialAgent`** — runs sub-agents in order (zero LLM calls, pure orchestration)
- **`LoopAgent`** — repeats sub-agents until escalation (maps to `while market_is_open()`)
- **`LlmAgent`** — the actual LLM reasoning node with tools
- **`BaseAgent`** — custom non-LLM agent (for time/P&L checks)

```
root_agent (SequentialAgent)
  ├── pre_market_agent (SequentialAgent)
  │     ├── diary_reader_agent (LlmAgent)      → reads past trades, outputs learnings
  │     ├── market_scanner_agent (LlmAgent)     → queries DB, assesses regime, shortlists
  │     ├── news_agent (LlmAgent)               → google_search only (ADK limitation)
  │     └── watchlist_finalizer_agent (LlmAgent) → consolidates into final watchlist
  │
  ├── trading_loop_agent (LoopAgent)
  │     ├── trader_agent (LlmAgent)             → THE primary trading brain, all tools
  │     │     before_tool_callback: risk_manager
  │     └── loop_controller (BaseAgent)          → checks time & P&L, adaptive sleep
  │
  └── eod_agent (LlmAgent)                      → square off, diary write, summary
```

**Why this structure:**
- **Pre-market as SequentialAgent:** Pipeline steps (diary → scan → news → finalize) run once in order. Each step writes to shared state via `output_key`.
- **News agent isolated:** Gemini's `google_search` cannot coexist with other tools in the same LlmAgent (ADK limitation). Also usable mid-day via `AgentTool` wrapper.
- **LoopAgent for trading:** Replaces the manual `while` loop. `loop_controller` (non-LLM) handles time/P&L checks and adaptive sleep — no LLM call wasted on clock-checking.
- **Single `trader_agent` with ALL tools:** One brain with full context. No context loss from agent transfers. MCP broker tools + native Python tools coexist in the same `tools` list.

### 6.2 Dynamic Instructions (Function, Not Static String)

The trader agent's instruction is a **function** that injects live state on every invocation:

```python
def trader_instruction(context: ReadonlyContext) -> str:
    state = context.state
    return f"""You are an expert Indian F&O options day trader.

    MODE: {"PAPER TRADING" if state.get("app:mode") == "paper" else "LIVE TRADING"}
    Current P&L: Rs {state.get("daily_pnl", 0)}
    Open Positions: {state.get("open_positions_count", 0)}
    Watchlist: {state.get("watchlist", [])}
    ...
    """
```

This replaces static system prompts — the agent always sees current state without explicit tool calls.

### 6.3 Risk Manager as `before_tool_callback`

The risk manager is implemented as ADK's `before_tool_callback`, which intercepts tool calls before execution:

```python
def risk_manager_callback(ctx, tool_name, tool_args) -> dict | None:
    if tool_name not in {"place_order", "modify_order"}:
        return None  # allow non-order tools

    # Check: daily loss, position count, time, ban list
    # Return rejection dict → LLM sees the reason and adjusts
    # Return None → tool call proceeds normally
```

When the callback returns a dict, ADK skips actual execution and returns it as the tool result. The LLM sees "REJECTED: daily loss limit reached" and adjusts behavior.

### 6.4 Session State Flow

ADK's session state is shared across all agents. Each agent reads/writes via `output_key` or `tool_context.state`:

```
diary_reader → state["diary_context"]
    ↓
market_scanner → state["watchlist_candidates"]
    ↓
news_agent → state["news_analysis"]
    ↓
watchlist_finalizer → state["watchlist"]
    ↓
trader_agent (reads all above, updates):
    → state["daily_pnl"]
    → state["open_positions_count"]
    → state["monitoring_interval"]
    → state["phase"]
```

### 6.5 Loop Controller (Non-LLM Agent)

A custom `BaseAgent` that checks market hours and P&L without burning an LLM call:

```python
class LoopController(BaseAgent):
    async def _run_async_impl(self, ctx):
        should_stop = (
            current_time >= square_off_time
            or daily_pnl <= -max_daily_loss
        )
        yield Event(actions=EventActions(escalate=should_stop))
        await asyncio.sleep(ctx.session.state.get("monitoring_interval", 120))
```

### 6.6 Monitoring Interval Logic (Agent-Decided)

The `trader_agent` instruction tells the LLM to update `state["monitoring_interval"]` based on conditions:

| Condition | Interval |
|-----------|----------|
| No open positions, scanning | 300s (5 minutes) |
| Position open, in profit | 180s (3 minutes) |
| Position near SL | 60s (1 minute) |
| P&L approaching daily limit | 60s (1 minute) |
| Last 30 min before square-off | 60s (1 minute) |

The `loop_controller` reads this value and sleeps accordingly. The LLM reasons about urgency; the controller enforces the timing.

### 6.7 Entry Point

```python
# main.py
async def main():
    runner = Runner(agent=root_agent, app_name="odta", session_service=InMemorySessionService())
    session = await session_service.create_session(
        app_name="odta", user_id="trader",
        state={"trade_date": today, "mode": config.mode, ...}
    )
    async for event in runner.run_async(user_id="trader", session_id=session.id,
        new_message=Content(role="user", parts=[Part(text="Begin trading day.")])):
        if event.is_final_response():
            print(f"Day complete: {event.content}")
```

### 6.8 Development with `adk web`

ADK provides a built-in web UI for interactive testing:

```bash
adk web odta/agents  # opens browser UI to chat with agent, inspect tool calls
```

Use `adk web` during development alongside the Next.js dashboard in production.

---

## 7. Risk Management Details

### 7.1 Pre-Trade Risk Check (Hardcoded Middleware)

Before any order is placed, the risk manager validates these non-negotiable rules:

1. **Daily loss check:** Current realized + unrealized loss < Rs 5,000
2. **Position count:** Open positions < 2
3. **Ban list check:** Symbol not in ban list
4. **Time check:** Not past square-off time
5. **Lot size check:** Quantity is valid F&O lot size

If any check fails, the order is rejected and the agent is informed why.

### 7.2 Intra-Trade Risk Management (Agent-Driven)

The agent decides all intra-trade risk management using its own judgment:

- **Stop-loss levels:** Agent determines SL based on chart analysis, ATR, support/resistance, option premium, and market regime. No hardcoded SL percentage.
- **Defensive mode:** Agent decides when to reduce risk appetite — e.g., after consecutive losses, in choppy markets, or when approaching daily loss limit. This is a reasoning decision, not a config threshold.
- **Re-evaluation triggers:** Agent decides when to re-evaluate urgently vs. on regular interval.
- **At -5,000 daily loss:** Hard stop (enforced by middleware), all positions squared off, agent stops trading.

### 7.3 Position Sizing (Agent-Driven)

- Agent determines position size based on: risk per trade (SL distance x lot size), conviction level, remaining daily loss budget
- Phase 1: Single lot trades to keep risk simple, but agent may reason about this
- Capital is not the constraint; risk per trade is

---

## 8. Daily Output: Summary & Diary Entry

At end of day, the agent produces:

```
═══════════════════════════════════════════════
  DAILY TRADING SUMMARY — 2025-01-28
═══════════════════════════════════════════════

Watchlist: RELIANCE, TATAMOTORS, HDFCBANK, INFY
Trades Taken: 2

Trade 1: RELIANCE 2500 CE
  Entry: 45.50 @ 10:15 AM | Exit: 62.00 @ 12:30 PM
  P&L: +4,125 (250 qty)
  Rationale: Breakout above 2480 resistance with volume
  Exit: Target hit at 2510 level

Trade 2: TATAMOTORS 800 PE
  Entry: 18.00 @ 01:15 PM | Exit: 14.50 @ 02:45 PM
  P&L: -2,100 (600 qty)
  Rationale: Breakdown below 805 support
  Exit: SL hit, stock reversed on market recovery

───────────────────────────────────────────────
  Net P&L: +2,025
  Win Rate: 1/2 (50%)
───────────────────────────────────────────────

Learnings:
- Afternoon reversals continue to be a risk; avoid
  late-day mean-reversion setups
- RELIANCE breakout thesis worked well; volume
  confirmation was key signal

Mistakes:
- TATAMOTORS entry was against broader market trend
  (Nifty was recovering). Should check index direction
  before contra trades.
═══════════════════════════════════════════════
```

---

## 9. Phase Plan

### Phase 1a — Foundation
- Project setup: pyproject.toml, config.yaml, ADK directory structure
- Git submodule: angel-one-mcp-server
- DB layer: DuckDB schema (ohlcv, trade_diary, decision_log), connection, seed F&O list
- Build all native tools: sql_agent, greeks, indicators, market_sentiment, trade_diary, decision_logger, paper_tracker
- Risk manager as `before_tool_callback`

### Phase 1b — Core Trading Agent (Incremental)
- Build `trader_agent` (LlmAgent) with all tools + MCP broker connection
- Build `loop_controller` (BaseAgent)
- Simple `root_agent` = LoopAgent(trader + loop_controller) — no pre-market/EOD yet
- Build `main.py` with ADK Runner
- Test with `adk web` (interactive debugging)
- Manually provide watchlist via initial state for testing

### Phase 1c — Pre-Market & EOD Agents
- Build `news_agent` (google_search)
- Build `pre_market_agent` pipeline (diary_reader → scanner → news → finalizer)
- Build `eod_agent` (diary write, summary)
- Assemble full `root_agent` (SequentialAgent: pre_market → trading_loop → eod)
- Full autonomous daily lifecycle working

### Phase 1d — Dashboard + Paper Trading Validation
- Next.js dashboard: live positions, trade history, workflow visualizer, diary
- Dashboard API routes reading from DuckDB
- Run full paper trading days, validate end-to-end

### Phase 2
- Chart generation + Gemini vision analysis
- Spread strategies (bull call spread, bear put spread)
- Smarter position sizing based on conviction level
- Telegram/WhatsApp alerts for trades and daily summary
- Performance analytics in dashboard
- Cloud scheduling (replace local sleep loop)

### Phase 3
- Multi-leg strategies (straddles, strangles, iron condors)
- Index options (Nifty, BankNifty)
- Portfolio-level Greeks management
- Backtesting framework using historical data
- Trade diary pattern recognition (auto-detect recurring mistakes)

---

## 10. Configuration

Minimal configuration — only infrastructure settings and absolute guardrails. All trading logic, thresholds, and heuristics are decided by the agent at runtime.

```yaml
# config.yaml

# --- Infrastructure (required) ---
llm:
  model: "gemini-2.0-flash"       # ADK handles multi-LLM natively
                                   # Options: gemini-2.0-flash, claude-sonnet-4-5-20250929, etc.

database:
  path: "/Users/bhaveshghodasara/Development/price-vol-pattern/data/stocks.duckdb"  # Existing OHLCV data

broker:
  mcp_server_path: "./angel-one-mcp-server"  # git submodule path
  # Credentials via environment variables:
  # ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_CODE, ANGEL_ONE_PASSWORD, ANGEL_ONE_TOTP_SECRET

# --- Absolute guardrails (safety only) ---
guardrails:
  max_daily_loss: 5000             # hard stop, non-negotiable
  max_open_positions: 2            # capital protection
  square_off_time: "15:00"         # no overnight risk
  pre_market_start: "08:45"        # when agent boots up

# --- Mode ---
mode: "paper"                      # paper | live
                                   # paper: MCP server runs with DRY_RUN_MODE=true
                                   # live: real order execution
```

**Design principle:** The agent decides everything else — defensive thresholds, volume filters, lookback periods, indicator parameters, position sizing, monitoring intervals. These are trading decisions, not configuration. The agent should apply its own judgment, adapt to market conditions, and learn from its trade diary.

---

## 11. Paper Trading Mode

For development and testing, the agent runs in paper trading mode (configured via `mode: "paper"` in config).

**How it works:**
- The Angel One MCP server has a built-in `DRY_RUN_MODE` — when enabled, `place_order`, `modify_order`, and `cancel_order` return simulated responses without hitting the real API
- Market data calls (LTP, candles, option chain) still hit the real Angel One API — **real data, simulated execution**
- A `PaperPositionTracker` (native Python tool) tracks cumulative positions and P&L in ADK session state, since the MCP server's dry run mode simulates individual orders but doesn't track portfolio state
- Trade diary entries are written identically to live mode
- The dashboard shows paper trades with a clear "PAPER" badge

**Transition to live:**
- Set `DRY_RUN_MODE=false` in MCP server environment
- Change `mode: "paper"` to `mode: "live"` in config.yaml
- The `trader_agent` uses `get_positions` (real broker) instead of `get_paper_positions`
- No code changes needed — same agent, same tools, different mode

---

## 12. Dashboard (Next.js)

A web-based UI for monitoring and reviewing the agent's activity.

### 12.1 Pages

| Page | Purpose |
|------|---------|
| **Live Dashboard** | Current open positions, unrealized P&L, daily P&L, agent status (phase), market regime |
| **Trade History** | All closed trades with entry/exit rationale, P&L, tags, filterable by date/stock |
| **Workflow Visualizer** | Timeline of agent decisions for the current day — what it analyzed, why it picked/rejected stocks, why it entered/exited. Shows the reasoning chain. |
| **Trade Diary** | Daily summaries, learnings, mistakes — rendered from DB |
| **Performance** | (Phase 2) Win rate, P&L curve, drawdown, strategy breakdown |

### 12.2 Workflow Visualizer (Key Feature)

This is critical for understanding and trusting the agent. It shows:

```
09:00 ── Pre-Market Analysis
         ├── Market Regime: Nifty bullish, above 22000 support
         ├── Sectors: IT +1.2%, Banking flat, Auto strong
         ├── Scanned 180 F&O stocks (22 in ban, excluded)
         ├── Shortlisted: RELIANCE, TATAMOTORS, INFY, WIPRO, M&M
         └── Reasoning: "Volume spike in auto sector, TATAMOTORS near breakout..."

09:20 ── Trade Planning
         ├── RELIANCE: Bias bullish, but resistance at 2500, skip
         ├── TATAMOTORS: Breakout above 820, strong volume ✅
         │   ├── Option: 840 CE, premium 18, IV 28%, delta 0.4
         │   ├── SL: 12 (based on support at 815)
         │   └── Target: 30 (resistance at 850)
         └── INFY: Sideways, no clear setup, skip

09:35 ── Trade Executed
         └── BUY TATAMOTORS 840 CE x 600 @ 18.00

10:05 ── Monitoring
         ├── TATAMOTORS at 828, option at 21.50, P&L: +2,100
         └── Decision: HOLD, trailing SL to 16
         ...
```

This is powered by a structured decision log that the agent writes at every step. Each log entry contains: timestamp, phase, action, reasoning, data points used.

### 12.3 API Backend

The Next.js app reads from the same database the agent writes to. A lightweight API layer (Next.js API routes or separate FastAPI) exposes:

- `GET /api/positions` — current open positions
- `GET /api/trades?date=2025-01-28` — trades for a date
- `GET /api/workflow?date=2025-01-28` — decision log for workflow visualizer
- `GET /api/diary?date=2025-01-28` — trade diary entry
- `GET /api/status` — agent status (phase, P&L, mode)

---

## 13. Decision Log Schema

For the workflow visualizer, the agent writes structured decision logs:

```sql
CREATE TABLE decision_log (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP,
    trade_date DATE,
    phase VARCHAR,              -- pre_market / planning / execution / monitoring / eod
    action_type VARCHAR,        -- analysis / stock_selection / trade_entry / trade_exit / monitoring / skip
    symbol VARCHAR,             -- NULL for market-level decisions
    summary TEXT,               -- one-line summary of the decision
    reasoning TEXT,             -- detailed reasoning (agent's thought process)
    data_points TEXT,           -- JSON: indicators, prices, levels used in decision
    outcome VARCHAR             -- result of the action (if applicable)
);
```

---

## 14. Directory Structure

```
options-day-trader-agent/
├── pyproject.toml                     # Dependencies: google-adk, duckdb, pandas-ta, etc.
├── config.yaml                        # Minimal config (guardrails + infra only)
├── main.py                            # Entry point: boots ADK Runner, starts trading day
│
├── odta/                              # Main Python package
│   ├── __init__.py
│   ├── agents/                        # ADK agent definitions
│   │   ├── __init__.py
│   │   ├── agent.py                   # ADK entry point: exports root_agent (for adk web)
│   │   ├── root_agent.py             # Assembles full agent tree + MCP connection
│   │   ├── pre_market.py             # Pre-market SequentialAgent pipeline
│   │   ├── trader.py                 # Core trading LlmAgent (primary brain)
│   │   ├── news.py                   # News LlmAgent (google_search only)
│   │   ├── loop_controller.py        # Non-LLM BaseAgent (time/P&L check, adaptive sleep)
│   │   └── eod.py                    # EOD LlmAgent (square off, diary write, summary)
│   ├── tools/                         # Native Python function tools
│   │   ├── __init__.py
│   │   ├── sql_agent.py              # query_database() — DuckDB queries
│   │   ├── greeks.py                 # calculate_greeks() — Black-Scholes
│   │   ├── indicators.py            # calculate_indicators() — pandas-ta
│   │   ├── charts.py                # generate_and_analyze_chart() — Phase 2
│   │   ├── market_sentiment.py      # get_market_regime(), get_sector_sentiment()
│   │   ├── trade_diary.py           # read_trade_diary(), write_trade_diary()
│   │   ├── decision_logger.py       # log_decision() — feeds workflow visualizer
│   │   └── paper_tracker.py         # Paper position/P&L tracking in session state
│   ├── risk/                          # Risk management (NOT an LLM tool)
│   │   ├── __init__.py
│   │   └── callbacks.py             # risk_manager_callback (ADK before_tool_callback)
│   ├── prompts/                       # System prompts (version-controlled, long text)
│   │   ├── trader.py                # trader_instruction() — dynamic function
│   │   ├── pre_market.py            # Pre-market agent prompts
│   │   ├── news.py                  # News analyst prompt
│   │   └── eod.py                   # EOD summary prompt
│   ├── db/                            # Database layer
│   │   ├── __init__.py
│   │   ├── connection.py            # DuckDB connection singleton
│   │   └── schema.py               # Table DDL (ohlcv, trade_diary, decision_log)
│   ├── models/                        # Pydantic data models
│   │   ├── __init__.py
│   │   ├── config.py               # Config model (loads config.yaml)
│   │   └── trade.py                # Trade, Position, Order models
│   └── utils/
│       ├── __init__.py
│       ├── time_helpers.py          # IST helpers, market hours check
│       └── logger.py               # Structured logging
│
├── angel-one-mcp-server/              # Git submodule → github.com/bhavesh0009/angel-one-mcp-server
│   └── src/angel_one_mcp/server.py
│
├── dashboard/                         # Next.js frontend
│   ├── package.json
│   ├── app/
│   │   ├── page.tsx                 # Live dashboard (positions, P&L, agent status)
│   │   ├── trades/page.tsx          # Trade history with rationale
│   │   ├── workflow/page.tsx        # Workflow visualizer (decision log timeline)
│   │   ├── diary/page.tsx           # Trade diary viewer
│   │   └── api/                     # API routes (reads from DuckDB)
│   │       ├── positions/route.ts
│   │       ├── trades/route.ts
│   │       ├── workflow/route.ts
│   │       ├── diary/route.ts
│   │       └── status/route.ts
│   └── components/
│       ├── PositionCard.tsx
│       ├── WorkflowTimeline.tsx
│       └── PnLChart.tsx
│
├── data/
│   └── trading.db                    # DuckDB database file
├── logs/
│   └── 2025-01-28.log
└── tests/
    ├── test_risk_callbacks.py
    ├── test_sql_agent.py
    ├── test_greeks.py
    ├── test_indicators.py
    ├── test_loop_controller.py
    └── test_paper_tracker.py
```

**ADK convention:** `odta/agents/agent.py` exports `root_agent`. This enables `adk web odta/agents` for the built-in dev UI.

---

## 15. Key Design Decisions

1. **Google ADK as orchestration framework** — provides agentic loop, MCP support, session state, multi-LLM, and dev UI out of the box. Eliminates the need for custom agent loops, LLM abstraction layers, and state management code.

2. **Composable agent tree, single trading brain** — ADK's `SequentialAgent` and `LoopAgent` handle orchestration (zero LLM calls). The actual reasoning happens in one `trader_agent` LlmAgent with all tools, preserving full context. Sub-agents exist only where ADK limitations require it (google_search isolation) or where separation genuinely simplifies (pre-market pipeline).

3. **Risk manager as `before_tool_callback`** — ADK's callback mechanism intercepts order tool calls before execution. Returns rejection dict if rules violated — the LLM sees the reason and adjusts. Not a tool the LLM can invoke or bypass.

4. **Reuse existing Angel One MCP server** — connected as a git submodule via ADK's `McpToolset`. 24 tools already working. Real market data + simulated execution via `DRY_RUN_MODE` for paper trading. No code duplication.

5. **Gemini Google Search for news** — native Gemini tool, no external news API needed. Isolated in its own `news_agent` (ADK limitation), also usable mid-day via `AgentTool` wrapper.

6. **Minimal configuration, maximum agent autonomy** — trading logic lives in the agent's reasoning, not in config files. The agent decides stop-losses, volume filters, defensive thresholds, and indicator parameters. Config only contains infrastructure settings and safety guardrails.

7. **LLM-agnostic via ADK** — switching from Gemini to Claude is a `model` parameter change. No custom abstraction layer needed. ADK natively supports Gemini, Claude, Ollama, vLLM, LiteLLM.

8. **Trade diary as agent memory** — the agent reads its own past trades and learnings at the start of each day. Persistent memory across sessions without complex vector DB setups.

9. **Agent never stops scanning** — if no trade is found by 9:30, the agent continues looking for setups throughout the day until 2:45 PM.

10. **Market-first, stock-second** — always assess overall market regime (Nifty/BankNifty) and sector sentiment before individual stock analysis.

11. **Paper trading by default** — MCP server's `DRY_RUN_MODE` + `PaperPositionTracker`. Real market data, simulated execution. Live mode is a config/env switch.

12. **Workflow transparency via decision log** — every decision logged with reasoning, powering the dashboard's workflow visualizer.

13. **Monthly expiry only (Indian market)** — agent considers theta decay and may choose next month's expiry when current expiry is near.

14. **Incremental build approach** — start with `trader_agent` + `loop_controller` only. Add pre-market and EOD agents after core trading works. Dashboard built alongside.

15. **`adk web` for dev, Next.js for production** — ADK's built-in web UI for interactive debugging during development. Next.js dashboard for monitoring paper/live trading.

---

## 16. Resolved Questions

| Question | Decision |
|----------|----------|
| Paper trading mode? | Yes, local simulation with real market data. `PaperBroker` implements same interface as live broker. |
| Alerting? | Phase 1: log to DB only, view via dashboard. Phase 2: add Telegram/WhatsApp alerts. |
| Intraday data gap? | Broker API provides LTP, 5min/15min candles, and market depth in real-time. DB is for historical daily data only. |
| Multiple expiries? | Monthly only (Indian stock options). Agent decides current vs next month based on days-to-expiry and theta impact. |
| Market regime detection? | Yes, built as a core tool (Market Sentiment & Regime). Nifty for all stocks, BankNifty additionally for financial sector stocks. |
