# Technical Implementation Document — ODTA

This document provides implementation-level details for building the Options Day Trader Agent. It complements the PRD (product-level requirements) with concrete code patterns, schemas, API contracts, and build instructions.

---

## 1. Project Setup

### 1.1 Dependencies

```toml
# pyproject.toml
[project]
name = "odta"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "google-adk>=0.5.0",
    "google-genai",
    "duckdb>=1.0.0",
    "pandas>=2.0",
    "pandas-ta>=0.3.14",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "pytz",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "ruff",
]
phase2 = [
    "mplfinance",
    "plotly",
]

[tool.ruff]
line-length = 100
```

### 1.2 Environment Variables

```bash
# .env (never committed)
GOOGLE_API_KEY="your-gemini-api-key"

# Angel One credentials (used by MCP server)
ANGEL_ONE_API_KEY="your-api-key"
ANGEL_ONE_CLIENT_CODE="your-client-code"
ANGEL_ONE_PASSWORD="your-password"
ANGEL_ONE_TOTP_SECRET="your-totp-secret"

# Safety
DRY_RUN_MODE="true"          # paper trading
MAX_ORDER_QUANTITY="1"        # lot limit during testing
```

### 1.3 Git Submodule Setup

```bash
git submodule add https://github.com/bhavesh0009/angel-one-mcp-server.git
git submodule update --init
```

---

## 2. Database Schema

### 2.1 Existing Database

The OHLCV data already exists at: `/Users/bhaveshghodasara/Development/price-vol-pattern/data/stocks.duckdb`

**Existing tables (DO NOT recreate):**

```sql
-- daily_ohlcv: 57,192 rows, 208 F&O stocks, Jan 2025 – Feb 2026
-- Columns: symbol, date, series, open, high, low, close, prev_close,
--          volume, value, vwap, trades, delivery_volume, delivery_pct

-- fno_stocks: 208 F&O eligible stocks
-- Columns: symbol, company_name, lot_size, last_updated
-- NOTE: lot_size is currently 0 for all — needs to be populated

-- index_ohlcv: Nifty 50 data, 275 rows
-- Columns: index_name, date, open, high, close, low
-- NOTE: Only Nifty 50 — BankNifty needs to be added
```

**Data gaps to fix before Phase 1:**
1. Populate `fno_stocks.lot_size` with actual lot sizes from NSE
2. Add `sector` and `industry` columns to `fno_stocks` for sector analysis
3. Add BankNifty data to `index_ohlcv`
4. Add `volume` column to `index_ohlcv` (if available)

### 2.2 New Tables to Create (`odta/db/schema.py`)

```sql

-- Trade diary (agent memory across days)
CREATE TABLE IF NOT EXISTS trade_diary (
    id INTEGER PRIMARY KEY,
    trade_date DATE NOT NULL,
    symbol VARCHAR,
    option_symbol VARCHAR,
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    entry_price DECIMAL(12,2),
    exit_price DECIMAL(12,2),
    quantity INTEGER,
    direction VARCHAR,              -- BUY_CE / BUY_PE
    pnl DECIMAL(12,2),
    entry_rationale TEXT,
    exit_rationale TEXT,
    market_conditions TEXT,
    learnings TEXT,
    mistakes TEXT,
    daily_summary TEXT,
    tags VARCHAR
);

-- Decision log (powers workflow visualizer)
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    trade_date DATE NOT NULL,
    phase VARCHAR NOT NULL,         -- pre_market / planning / execution / monitoring / eod
    action_type VARCHAR NOT NULL,   -- analysis / stock_selection / trade_entry / trade_exit / monitoring / skip
    symbol VARCHAR,                 -- NULL for market-level decisions
    summary TEXT NOT NULL,
    reasoning TEXT,
    data_points TEXT,               -- JSON string
    outcome VARCHAR
);

-- Paper trading positions (for paper mode only)
CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY,
    trade_date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    option_symbol VARCHAR NOT NULL,
    transaction_type VARCHAR NOT NULL,  -- BUY / SELL
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(12,2) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_price DECIMAL(12,2),
    exit_time TIMESTAMP,
    status VARCHAR DEFAULT 'OPEN',      -- OPEN / CLOSED
    pnl DECIMAL(12,2)
);
```

### 2.2 Connection Singleton (`odta/db/connection.py`)

```python
import duckdb
from functools import lru_cache

@lru_cache(maxsize=1)
def get_db_connection(db_path: str = None) -> duckdb.DuckDBPyConnection:
    if db_path is None:
        from odta.models.config import load_config
        db_path = load_config().database.path
    conn = duckdb.connect(db_path)
    return conn
```

---

## 3. Tool Implementations

### 3.1 SQL Agent (`odta/tools/sql_agent.py`)

```python
def query_database(sql: str, explanation: str) -> dict:
    """Execute a read-only SQL query against the trading database.

    Use this to query historical OHLCV data, F&O securities list, ban list,
    and trade diary. Always provide an explanation of why you need this data.

    Available tables:
    - daily_ohlcv: symbol, date, series, open, high, low, close, prev_close, volume, value, vwap, trades, delivery_volume, delivery_pct
    - fno_stocks: symbol, company_name, lot_size, sector, industry, last_updated
    - index_ohlcv: index_name, date, open, high, close, low (Nifty 50, BankNifty)
    - ban_list: symbol, ban_date
    - trade_diary: id, trade_date, symbol, option_symbol, entry/exit details, rationale, learnings
    - decision_log: id, timestamp, trade_date, phase, action_type, symbol, summary, reasoning

    Args:
        sql: SQL query to execute. Must be a SELECT statement.
        explanation: Why this query is needed for the current trading decision.

    Returns:
        dict with columns, rows, row_count, and status
    """
    sql_stripped = sql.strip()
    if not sql_stripped.upper().startswith("SELECT"):
        return {"status": "error", "reason": "Only SELECT queries are allowed."}

    try:
        conn = get_db_connection()
        result = conn.execute(sql_stripped).fetchall()
        columns = [desc[0] for desc in conn.description]
        return {
            "status": "success",
            "columns": columns,
            "rows": [list(row) for row in result],
            "row_count": len(result),
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
```

### 3.2 Greeks Calculator (`odta/tools/greeks.py`)

```python
import math
from scipy.stats import norm

def calculate_greeks(
    spot_price: float,
    strike_price: float,
    expiry_days: int,
    option_premium: float,
    option_type: str,
    risk_free_rate: float = 0.07,
) -> dict:
    """Calculate option Greeks (Delta, Gamma, Theta, Vega) and Implied Volatility.

    Uses Black-Scholes model. Useful for evaluating option pricing and risk.

    Args:
        spot_price: Current price of the underlying stock.
        strike_price: Strike price of the option.
        expiry_days: Number of calendar days until expiry.
        option_premium: Current market premium of the option.
        option_type: "CE" for Call, "PE" for Put.
        risk_free_rate: Annual risk-free rate (default 0.07 for India).

    Returns:
        dict with iv, delta, gamma, theta, vega values
    """
    T = max(expiry_days / 365.0, 0.001)
    is_call = option_type.upper() == "CE"

    # Newton-Raphson for IV
    iv = _implied_volatility(spot_price, strike_price, T, risk_free_rate, option_premium, is_call)

    # Greeks
    d1 = (math.log(spot_price / strike_price) + (risk_free_rate + 0.5 * iv**2) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)

    if is_call:
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1

    gamma = norm.pdf(d1) / (spot_price * iv * math.sqrt(T))
    vega = spot_price * norm.pdf(d1) * math.sqrt(T) / 100  # per 1% move in IV

    if is_call:
        theta = (-(spot_price * norm.pdf(d1) * iv) / (2 * math.sqrt(T))
                 - risk_free_rate * strike_price * math.exp(-risk_free_rate * T) * norm.cdf(d2)) / 365
    else:
        theta = (-(spot_price * norm.pdf(d1) * iv) / (2 * math.sqrt(T))
                 + risk_free_rate * strike_price * math.exp(-risk_free_rate * T) * norm.cdf(-d2)) / 365

    return {
        "status": "success",
        "iv": round(iv, 4),
        "iv_pct": f"{round(iv * 100, 2)}%",
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 2),
        "vega": round(vega, 2),
        "expiry_days": expiry_days,
    }


def _implied_volatility(S, K, T, r, market_price, is_call, max_iter=100, tol=1e-6):
    """Newton-Raphson method for implied volatility."""
    sigma = 0.3  # initial guess
    for _ in range(max_iter):
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if is_call:
            price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        vega = S * norm.pdf(d1) * math.sqrt(T)
        if vega < 1e-12:
            break
        sigma -= (price - market_price) / vega
        if abs(price - market_price) < tol:
            break
    return max(sigma, 0.01)
```

### 3.3 Technical Indicators (`odta/tools/indicators.py`)

```python
import pandas as pd
import pandas_ta as ta

def calculate_indicator(symbol: str, indicator: str, period: int = 14, lookback_days: int = 100) -> dict:
    """Calculate a technical indicator for a stock using historical daily data.

    Supported indicators: RSI, MACD, SMA, EMA, ATR, ADX, BBANDS (Bollinger Bands),
    SUPERTREND, STOCH (Stochastic), OBV, VWAP, and any indicator supported by pandas-ta.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE").
        indicator: Indicator name (e.g., "RSI", "MACD", "SMA").
        period: Period/length for the indicator (default 14).
        lookback_days: How many days of historical data to use (default 100).

    Returns:
        dict with indicator values for recent dates
    """
    conn = get_db_connection()
    df = conn.execute(f"""
        SELECT date, open, high, low, close, volume
        FROM daily_ohlcv
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT ?
    """, [symbol, lookback_days]).fetchdf()

    if df.empty:
        return {"status": "error", "reason": f"No data found for {symbol}"}

    df = df.sort_values("date").reset_index(drop=True)

    indicator_upper = indicator.upper()
    try:
        if indicator_upper == "RSI":
            result = ta.rsi(df["close"], length=period)
        elif indicator_upper == "SMA":
            result = ta.sma(df["close"], length=period)
        elif indicator_upper == "EMA":
            result = ta.ema(df["close"], length=period)
        elif indicator_upper == "ATR":
            result = ta.atr(df["high"], df["low"], df["close"], length=period)
        elif indicator_upper == "ADX":
            result = ta.adx(df["high"], df["low"], df["close"], length=period)
        elif indicator_upper == "MACD":
            result = ta.macd(df["close"])
        elif indicator_upper == "BBANDS":
            result = ta.bbands(df["close"], length=period)
        elif indicator_upper == "SUPERTREND":
            result = ta.supertrend(df["high"], df["low"], df["close"], length=period)
        elif indicator_upper == "STOCH":
            result = ta.stoch(df["high"], df["low"], df["close"])
        elif indicator_upper == "OBV":
            result = ta.obv(df["close"], df["volume"])
        else:
            # Try generic pandas-ta
            strategy = ta.Strategy(name="custom", ta=[{"kind": indicator.lower(), "length": period}])
            df.ta.strategy(strategy)
            result = df.iloc[:, 6:]  # columns after OHLCV

        if isinstance(result, pd.Series):
            result = result.to_frame()

        # Return last 10 values
        recent = pd.concat([df[["date", "close"]], result], axis=1).tail(10)
        return {
            "status": "success",
            "symbol": symbol,
            "indicator": indicator,
            "period": period,
            "values": recent.to_dict(orient="records"),
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
```

### 3.4 Market Sentiment (`odta/tools/market_sentiment.py`)

```python
def get_market_regime(index: str = "NIFTY") -> dict:
    """Assess overall market direction and regime for Nifty or BankNifty.

    Analyzes recent daily data to classify the market as bullish/bearish/sideways
    and trending/ranging/volatile. Essential context before any stock-level analysis.

    For financial sector stocks, also check BankNifty.

    Args:
        index: "NIFTY" or "BANKNIFTY"

    Returns:
        dict with trend, regime, key_levels, recent_performance, and vix (if available)
    """
    conn = get_db_connection()
    # Map index to index_name in DB
    index_map = {"NIFTY": "NIFTY 50", "BANKNIFTY": "NIFTY BANK"}
    index_name = index_map.get(index.upper(), index)

    df = conn.execute("""
        SELECT date, open, high, low, close
        FROM index_ohlcv WHERE index_name = ?
        ORDER BY date DESC LIMIT 50
    """, [index_name]).fetchdf()

    if df.empty:
        return {"status": "error", "reason": f"No data for {symbol}"}

    df = df.sort_values("date").reset_index(drop=True)

    # Calculate indicators for regime detection
    sma_20 = df["close"].rolling(20).mean().iloc[-1]
    sma_50 = df["close"].rolling(50).mean().iloc[-1] if len(df) >= 50 else None
    rsi = ta.rsi(df["close"], length=14).iloc[-1]
    atr = ta.atr(df["high"], df["low"], df["close"], length=14).iloc[-1]
    current = df["close"].iloc[-1]
    avg_range = (df["high"] - df["low"]).mean()

    # Trend classification
    if current > sma_20 and (sma_50 is None or sma_20 > sma_50):
        trend = "bullish"
    elif current < sma_20 and (sma_50 is None or sma_20 < sma_50):
        trend = "bearish"
    else:
        trend = "sideways"

    # Regime classification
    recent_atr = ta.atr(df["high"], df["low"], df["close"], length=5).iloc[-1]
    if recent_atr > atr * 1.3:
        regime = "volatile"
    elif abs(current - sma_20) / current < 0.01:
        regime = "ranging"
    else:
        regime = "trending"

    # Key levels
    recent_high = df["high"].tail(20).max()
    recent_low = df["low"].tail(20).min()

    return {
        "status": "success",
        "index": index,
        "current_price": round(current, 2),
        "trend": trend,
        "regime": regime,
        "rsi": round(rsi, 2),
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2) if sma_50 else None,
        "atr_14": round(atr, 2),
        "key_levels": {
            "resistance": round(recent_high, 2),
            "support": round(recent_low, 2),
        },
        "5d_change_pct": round((current - df["close"].iloc[-6]) / df["close"].iloc[-6] * 100, 2) if len(df) >= 6 else None,
    }


def get_sector_sentiment(sector: str) -> dict:
    """Get sentiment for a specific sector by analyzing its constituent stocks.

    Args:
        sector: Sector name (e.g., "Banking", "IT", "Auto", "Pharma")

    Returns:
        dict with top gainers, losers, and sector trend assessment
    """
    conn = get_db_connection()

    # Get F&O stocks in this sector
    stocks = conn.execute("""
        SELECT f.symbol, o.close, o.open,
               ROUND((o.close - o.open) / o.open * 100, 2) as day_change_pct
        FROM fno_stocks f
        JOIN daily_ohlcv o ON f.symbol = o.symbol
        WHERE f.sector = ? AND o.date = (SELECT MAX(date) FROM daily_ohlcv)
        ORDER BY day_change_pct DESC
    """, [sector]).fetchall()

    if not stocks:
        return {"status": "error", "reason": f"No stocks found for sector: {sector}"}

    gainers = [{"symbol": s[0], "change": f"{s[3]}%"} for s in stocks if s[3] > 0][:3]
    losers = [{"symbol": s[0], "change": f"{s[3]}%"} for s in stocks if s[3] < 0][-3:]
    avg_change = sum(s[3] for s in stocks) / len(stocks)

    if avg_change > 0.5:
        trend = "bullish"
    elif avg_change < -0.5:
        trend = "bearish"
    else:
        trend = "neutral"

    return {
        "status": "success",
        "sector": sector,
        "sector_trend": trend,
        "avg_change_pct": round(avg_change, 2),
        "top_gainers": gainers,
        "top_losers": losers,
        "stock_count": len(stocks),
    }
```

### 3.5 Trade Diary (`odta/tools/trade_diary.py`)

```python
def read_trade_diary(last_n_trades: int = 15, include_daily_summaries: bool = True) -> dict:
    """Read recent trades and learnings from the trade diary.

    Use this at the start of each day to review past performance, identify
    recurring patterns, and avoid repeating mistakes.

    Args:
        last_n_trades: Number of recent trades to retrieve (default 15).
        include_daily_summaries: Whether to include daily summary entries.

    Returns:
        dict with recent trades, common patterns, and learnings
    """
    conn = get_db_connection()

    trades = conn.execute("""
        SELECT trade_date, symbol, option_symbol, direction, entry_price, exit_price,
               quantity, pnl, entry_rationale, exit_rationale, learnings, mistakes, tags
        FROM trade_diary
        WHERE symbol IS NOT NULL
        ORDER BY trade_date DESC, entry_time DESC
        LIMIT ?
    """, [last_n_trades]).fetchall()

    columns = ["trade_date", "symbol", "option_symbol", "direction", "entry_price",
               "exit_price", "quantity", "pnl", "entry_rationale", "exit_rationale",
               "learnings", "mistakes", "tags"]

    result = {"status": "success", "trades": [dict(zip(columns, t)) for t in trades]}

    if include_daily_summaries:
        summaries = conn.execute("""
            SELECT DISTINCT trade_date, daily_summary, market_conditions
            FROM trade_diary
            WHERE daily_summary IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 5
        """).fetchall()
        result["daily_summaries"] = [
            {"date": s[0], "summary": s[1], "conditions": s[2]} for s in summaries
        ]

    return result


def write_trade_diary(
    trade_date: str,
    symbol: str,
    option_symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    pnl: float,
    entry_rationale: str,
    exit_rationale: str,
    market_conditions: str = "",
    learnings: str = "",
    mistakes: str = "",
    daily_summary: str = "",
    tags: str = "",
) -> dict:
    """Write a trade entry or daily summary to the trade diary.

    Call this after exiting a trade or at end of day for the daily summary.

    Args:
        trade_date: Date of the trade (YYYY-MM-DD).
        symbol: Stock symbol.
        option_symbol: Full option symbol (e.g., RELIANCE25JAN2500CE).
        direction: BUY_CE or BUY_PE.
        entry_price: Entry premium price.
        exit_price: Exit premium price.
        quantity: Number of shares/lots traded.
        pnl: Profit/loss in rupees.
        entry_rationale: Why the trade was entered.
        exit_rationale: Why the trade was exited.
        market_conditions: Overall market view during the trade.
        learnings: What was learned from this trade.
        mistakes: What went wrong (self-critique).
        daily_summary: End-of-day summary (one per day).
        tags: Comma-separated tags (e.g., "breakout,momentum").

    Returns:
        dict with status and entry id
    """
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO trade_diary
        (trade_date, symbol, option_symbol, direction, entry_price, exit_price,
         quantity, pnl, entry_rationale, exit_rationale, market_conditions,
         learnings, mistakes, daily_summary, tags, entry_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, [trade_date, symbol, option_symbol, direction, entry_price, exit_price,
          quantity, pnl, entry_rationale, exit_rationale, market_conditions,
          learnings, mistakes, daily_summary, tags])

    return {"status": "success", "message": f"Trade diary entry written for {symbol}"}
```

### 3.6 Decision Logger (`odta/tools/decision_logger.py`)

```python
def log_decision(
    phase: str,
    action_type: str,
    summary: str,
    reasoning: str,
    symbol: str = "",
    data_points: str = "{}",
    outcome: str = "",
) -> dict:
    """Log a trading decision for the workflow visualizer dashboard.

    Call this after EVERY significant decision: market analysis, stock screening,
    trade entry/exit, monitoring updates, or skip decisions.

    Args:
        phase: Current phase — pre_market / planning / execution / monitoring / eod
        action_type: Type — analysis / stock_selection / trade_entry / trade_exit / monitoring / skip
        summary: One-line summary of the decision.
        reasoning: Detailed reasoning and thought process behind the decision.
        symbol: Stock symbol (leave empty for market-level decisions).
        data_points: JSON string of indicators, prices, and levels used in the decision.
        outcome: Result of the action, if applicable.

    Returns:
        dict with status confirmation
    """
    from datetime import date
    conn = get_db_connection()
    conn.execute("""
        INSERT INTO decision_log (trade_date, phase, action_type, symbol, summary, reasoning, data_points, outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [date.today().isoformat(), phase, action_type, symbol or None, summary, reasoning, data_points, outcome])

    return {"status": "success", "message": f"Decision logged: {summary}"}
```

### 3.7 Paper Position Tracker (`odta/tools/paper_tracker.py`)

```python
from google.adk.tools import ToolContext

def get_paper_positions(tool_context: ToolContext) -> dict:
    """Get current paper trading positions and P&L.

    Use this instead of get_positions when in paper trading mode.
    Returns simulated positions tracked locally.

    Returns:
        dict with open positions, closed positions today, and total P&L
    """
    conn = get_db_connection()
    from datetime import date

    open_positions = conn.execute("""
        SELECT symbol, option_symbol, transaction_type, quantity, entry_price, entry_time
        FROM paper_positions
        WHERE trade_date = ? AND status = 'OPEN'
    """, [date.today().isoformat()]).fetchall()

    closed_today = conn.execute("""
        SELECT symbol, option_symbol, entry_price, exit_price, quantity, pnl
        FROM paper_positions
        WHERE trade_date = ? AND status = 'CLOSED'
    """, [date.today().isoformat()]).fetchall()

    total_pnl = sum(c[5] for c in closed_today) if closed_today else 0

    return {
        "status": "success",
        "open_positions": [
            {"symbol": p[0], "option_symbol": p[1], "type": p[2],
             "qty": p[3], "entry_price": p[4], "entry_time": str(p[5])}
            for p in open_positions
        ],
        "closed_today": [
            {"symbol": c[0], "option_symbol": c[1], "entry": c[2],
             "exit": c[3], "qty": c[4], "pnl": c[5]}
            for c in closed_today
        ],
        "open_count": len(open_positions),
        "realized_pnl": total_pnl,
    }


def record_paper_trade(
    symbol: str,
    option_symbol: str,
    transaction_type: str,
    quantity: int,
    price: float,
    action: str,
) -> dict:
    """Record a paper trade entry or exit.

    Called by the after_tool_callback when place_order succeeds in paper mode.

    Args:
        symbol: Stock symbol.
        option_symbol: Full option symbol.
        transaction_type: BUY or SELL.
        quantity: Number of shares.
        price: Execution price.
        action: "ENTRY" or "EXIT"

    Returns:
        dict with status
    """
    from datetime import date, datetime
    conn = get_db_connection()

    if action == "ENTRY":
        conn.execute("""
            INSERT INTO paper_positions (trade_date, symbol, option_symbol, transaction_type, quantity, entry_price, entry_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """, [date.today().isoformat(), symbol, option_symbol, transaction_type, quantity, price, datetime.now().isoformat()])
    elif action == "EXIT":
        # Find matching open position and close it
        position = conn.execute("""
            SELECT id, entry_price, quantity FROM paper_positions
            WHERE option_symbol = ? AND status = 'OPEN'
            ORDER BY entry_time DESC LIMIT 1
        """, [option_symbol]).fetchone()

        if position:
            pnl = (price - position[1]) * position[2]
            if transaction_type == "SELL":
                pnl = (price - position[1]) * position[2]
            conn.execute("""
                UPDATE paper_positions SET exit_price = ?, exit_time = ?, status = 'CLOSED', pnl = ?
                WHERE id = ?
            """, [price, datetime.now().isoformat(), pnl, position[0]])

    return {"status": "success", "action": action}
```

---

## 4. Agent Definitions

### 4.1 Root Agent (`odta/agents/root_agent.py`)

```python
import os
from google.adk.agents import SequentialAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from odta.agents.pre_market import build_pre_market_agent
from odta.agents.trader import build_trader_agent
from odta.agents.loop_controller import LoopController
from odta.agents.eod import build_eod_agent
from odta.models.config import load_config


def _build_broker_toolset(config) -> McpToolset:
    """Connect to Angel One MCP server."""
    mcp_path = config.broker.mcp_server_path
    is_paper = config.mode == "paper"

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="python",
                args=["-m", "angel_one_mcp.server"],
                cwd=os.path.abspath(mcp_path),
                env={
                    **os.environ,
                    "DRY_RUN_MODE": "true" if is_paper else "false",
                    "MAX_ORDER_QUANTITY": str(config.guardrails.get("max_lot_multiplier", 1)),
                },
            )
        ),
    )


def build_root_agent():
    config = load_config()
    broker_tools = _build_broker_toolset(config)

    pre_market = build_pre_market_agent(config)
    trader = build_trader_agent(config, broker_tools)
    loop_ctrl = LoopController(name="loop_controller")
    eod = build_eod_agent(config)

    # Trading loop: trader reasons → loop_controller checks time & sleeps → repeat
    from google.adk.agents import LoopAgent
    trading_loop = LoopAgent(
        name="trading_loop",
        sub_agents=[trader, loop_ctrl],
        max_iterations=300,  # safety cap (~10 hours at 2min avg)
    )

    return SequentialAgent(
        name="daily_session",
        sub_agents=[pre_market, trading_loop, eod],
    )
```

### 4.2 Trader Agent (`odta/agents/trader.py`)

```python
from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool

from odta.tools.sql_agent import query_database
from odta.tools.greeks import calculate_greeks
from odta.tools.indicators import calculate_indicator
from odta.tools.market_sentiment import get_market_regime, get_sector_sentiment
from odta.tools.trade_diary import read_trade_diary, write_trade_diary
from odta.tools.decision_logger import log_decision
from odta.tools.paper_tracker import get_paper_positions, record_paper_trade
from odta.risk.callbacks import risk_manager_callback
from odta.prompts.trader import trader_instruction
from odta.agents.news import build_news_agent


def build_trader_agent(config, broker_tools):
    news_agent = build_news_agent(config)
    news_tool = agent_tool.AgentTool(agent=news_agent)

    native_tools = [
        query_database,
        calculate_greeks,
        calculate_indicator,
        get_market_regime,
        get_sector_sentiment,
        read_trade_diary,
        write_trade_diary,
        log_decision,
        news_tool,
    ]

    # Add paper trading tools if in paper mode
    if config.mode == "paper":
        native_tools.extend([get_paper_positions, record_paper_trade])

    return LlmAgent(
        model=config.llm.model,
        name="trader",
        instruction=trader_instruction,
        tools=[broker_tools] + native_tools,
        before_tool_callback=risk_manager_callback,
        output_key="trader_output",
    )
```

### 4.3 News Agent (`odta/agents/news.py`)

```python
from google.adk.agents import LlmAgent
from google.adk.tools import google_search

NEWS_INSTRUCTION = """You are a market news analyst specializing in Indian stock markets.

When given a list of stocks or a query, search for:
1. Recent corporate announcements (earnings, results, dividends, splits)
2. Sector-level news and developments
3. Analyst upgrades/downgrades
4. Regulatory changes affecting the sector
5. Global events impacting Indian markets

For each stock, provide:
- Key news items with dates
- Sentiment classification: BULLISH / BEARISH / NEUTRAL
- Potential market impact: HIGH / MEDIUM / LOW

Be concise and factual. Cite sources."""


def build_news_agent(config):
    return LlmAgent(
        model=config.llm.model,
        name="news_analyst",
        instruction=NEWS_INSTRUCTION,
        tools=[google_search],
        output_key="news_analysis",
    )
```

### 4.4 Loop Controller (`odta/agents/loop_controller.py`)

```python
import asyncio
from datetime import datetime
import pytz
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions


class LoopController(BaseAgent):
    """Non-LLM agent that checks market hours and P&L limits.

    Runs after each trader_agent iteration. Sleeps for the adaptive
    monitoring interval, then checks if the trading loop should end.
    """

    async def _run_async_impl(self, ctx: InvocationContext):
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)
        current_time = now.strftime("%H:%M")

        square_off_time = ctx.session.state.get("app:square_off_time", "15:00")
        daily_pnl = ctx.session.state.get("daily_pnl", 0)
        max_loss = ctx.session.state.get("app:max_daily_loss", 5000)

        should_stop = (
            current_time >= square_off_time
            or daily_pnl <= -max_loss
        )

        if should_stop:
            reason = "square_off_time" if current_time >= square_off_time else "max_loss_breached"
            ctx.session.state["stop_reason"] = reason
            ctx.session.state["phase"] = "eod"

        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_stop),
        )

        if not should_stop:
            interval = ctx.session.state.get("monitoring_interval", 120)
            await asyncio.sleep(interval)
```

### 4.5 Pre-Market Pipeline (`odta/agents/pre_market.py`)

```python
from google.adk.agents import SequentialAgent, LlmAgent
from odta.tools.sql_agent import query_database
from odta.tools.trade_diary import read_trade_diary
from odta.tools.indicators import calculate_indicator
from odta.tools.market_sentiment import get_market_regime, get_sector_sentiment
from odta.agents.news import build_news_agent

DIARY_READER_INSTRUCTION = """You are reviewing the trade diary before the market opens.

Read the last 15 trades and recent daily summaries. Identify:
1. What setups have been working well recently?
2. What mistakes keep recurring?
3. Any stocks that have been consistently profitable?
4. Market conditions that led to losses vs. gains

Output a concise briefing for the trading day."""

SCANNER_INSTRUCTION = """You are scanning the F&O universe to find today's best trading candidates.

Steps:
1. First, check the ban list — exclude ALL banned securities
2. Assess market regime using get_market_regime for NIFTY (and BANKNIFTY if needed)
3. Identify strong/weak sectors using get_sector_sentiment
4. Query the database to find stocks with:
   - Unusual volume (above recent average — you decide the threshold)
   - Price near key support/resistance levels
   - Range expansion or breakout potential
   - Alignment with market/sector trend
5. Calculate relevant indicators (RSI, SMA, ATR) for shortlisted stocks

Output 3-8 candidate stocks with your directional bias and reasoning for each."""

FINALIZER_INSTRUCTION = """You are finalizing today's watchlist from the pre-market analysis.

You have access to:
- {diary_context}: Past trade learnings
- {watchlist_candidates}: Stocks identified by the scanner with technical analysis
- {news_analysis}: Recent news for the candidates

Narrow down to 2-5 final stocks. For each, specify:
1. Symbol
2. Directional bias (BULLISH / BEARISH)
3. Key levels to watch (support, resistance, entry zone)
4. Why this stock today (combining technicals + news + diary learnings)
5. Risk: what could go wrong

Drop any stock where news or diary learnings suggest caution."""


def build_pre_market_agent(config):
    diary_reader = LlmAgent(
        model=config.llm.model,
        name="diary_reader",
        instruction=DIARY_READER_INSTRUCTION,
        tools=[read_trade_diary, query_database],
        output_key="diary_context",
    )

    scanner = LlmAgent(
        model=config.llm.model,
        name="market_scanner",
        instruction=SCANNER_INSTRUCTION,
        tools=[query_database, calculate_indicator, get_market_regime, get_sector_sentiment],
        output_key="watchlist_candidates",
    )

    news = build_news_agent(config)

    finalizer = LlmAgent(
        model=config.llm.model,
        name="watchlist_finalizer",
        instruction=FINALIZER_INSTRUCTION,
        tools=[query_database],
        output_key="watchlist",
    )

    return SequentialAgent(
        name="pre_market_pipeline",
        sub_agents=[diary_reader, scanner, news, finalizer],
    )
```

### 4.6 EOD Agent (`odta/agents/eod.py`)

```python
from google.adk.agents import LlmAgent
from odta.tools.trade_diary import write_trade_diary
from odta.tools.decision_logger import log_decision

EOD_INSTRUCTION = """You are wrapping up the trading day. The trading loop has ended.

Reason for stopping: {stop_reason}

Your tasks:
1. Review all trades taken today (check positions and trade diary)
2. For each trade, write a diary entry with:
   - Entry/exit rationale
   - What you learned
   - What mistakes were made (be honest and self-critical)
3. Write a daily summary covering:
   - Market conditions today
   - What worked and what didn't
   - Key takeaways for tomorrow
4. Log the EOD summary as a decision

Be thorough in self-reflection. The diary is your memory for future trading days."""


def build_eod_agent(config):
    return LlmAgent(
        model=config.llm.model,
        name="eod_agent",
        instruction=EOD_INSTRUCTION,
        tools=[write_trade_diary, log_decision],
        output_key="daily_summary",
    )
```

### 4.7 ADK Entry Point (`odta/agents/agent.py`)

```python
"""ADK entry point. Exports root_agent for `adk web` and `adk run`."""

from odta.agents.root_agent import build_root_agent

root_agent = build_root_agent()
```

---

## 5. Risk Manager Callback (`odta/risk/callbacks.py`)

```python
from datetime import datetime
import pytz
from google.adk.agents.callback_context import CallbackContext


def risk_manager_callback(
    callback_context: CallbackContext,
    tool_name: str,
    tool_args: dict,
) -> dict | None:
    """Intercepts order-related tool calls and enforces risk guardrails.

    Returns None to allow the tool call, or a dict to reject it.
    When a dict is returned, ADK skips the tool execution and returns
    the dict as the tool result — the LLM sees the rejection reason.
    """
    ORDER_TOOLS = {"place_order", "modify_order"}

    if tool_name not in ORDER_TOOLS:
        return None  # non-order tools pass through

    state = callback_context.state
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    # Rule 1: Daily loss limit
    daily_pnl = state.get("daily_pnl", 0)
    max_loss = state.get("app:max_daily_loss", 5000)
    if daily_pnl <= -max_loss:
        return {
            "status": "REJECTED",
            "reason": f"Daily loss limit (Rs {max_loss}) breached. Current P&L: Rs {daily_pnl}. No further trading allowed.",
        }

    # Rule 2: Position count (only for new orders)
    if tool_name == "place_order":
        open_count = state.get("open_positions_count", 0)
        max_positions = state.get("app:max_open_positions", 2)
        if open_count >= max_positions:
            return {
                "status": "REJECTED",
                "reason": f"Max positions ({max_positions}) already open. Close an existing position first.",
            }

    # Rule 3: Time check (no new BUY entries near close)
    square_off_time = state.get("app:square_off_time", "15:00")
    if now.strftime("%H:%M") >= square_off_time:
        transaction_type = tool_args.get("transactiontype", tool_args.get("transaction_type", ""))
        if transaction_type.upper() == "BUY":
            return {
                "status": "REJECTED",
                "reason": f"Past square-off time ({square_off_time}). No new BUY orders allowed.",
            }

    # Rule 4: Ban list check
    symbol = tool_args.get("tradingsymbol", tool_args.get("symbol", ""))
    if symbol and _is_banned(symbol):
        return {
            "status": "REJECTED",
            "reason": f"{symbol} is in the F&O ban list. Cannot trade banned securities.",
        }

    return None  # all checks passed


def _is_banned(symbol: str) -> bool:
    """Check if a stock is in the ban list."""
    from odta.db.connection import get_db_connection
    from datetime import date

    # Extract base symbol from option symbol (e.g., RELIANCE25JAN2500CE → RELIANCE)
    conn = get_db_connection()
    base_symbols = conn.execute("""
        SELECT symbol FROM ban_list WHERE ban_date = ?
    """, [date.today().isoformat()]).fetchall()

    banned = {s[0].upper() for s in base_symbols}
    # Check if any banned symbol is a prefix of the trading symbol
    return any(symbol.upper().startswith(b) for b in banned)
```

---

## 6. Trader System Prompt (`odta/prompts/trader.py`)

```python
from google.adk.agents.readonly_context import ReadonlyContext
from datetime import datetime
import pytz


def trader_instruction(context: ReadonlyContext) -> str:
    state = context.state
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    mode = state.get("app:mode", "paper")
    daily_pnl = state.get("daily_pnl", 0)
    open_positions = state.get("open_positions_count", 0)
    max_loss = state.get("app:max_daily_loss", 5000)
    max_positions = state.get("app:max_open_positions", 2)
    square_off = state.get("app:square_off_time", "15:00")
    watchlist = state.get("watchlist", "Not set yet")
    phase = state.get("phase", "trading")

    return f"""You are an expert Indian F&O options day trader operating autonomously.

=== MODE ===
{"🔵 PAPER TRADING — simulated execution, real market data" if mode == "paper" else "🔴 LIVE TRADING — real money, real consequences"}

=== CURRENT STATE ({now.strftime('%H:%M IST')}) ===
Phase: {phase}
Daily P&L: Rs {daily_pnl:,.0f}
Open Positions: {open_positions} / {max_positions}
Remaining Loss Budget: Rs {max_loss + daily_pnl:,.0f}
Watchlist: {watchlist}

=== RISK GUARDRAILS (enforced by system — you cannot override) ===
- Max daily loss: Rs {max_loss:,} (hard stop, all positions squared off)
- Max open positions: {max_positions}
- Square off: {square_off} IST (no new BUY after this time)
- Banned securities: automatically rejected

=== YOUR RESPONSIBILITIES ===

1. **Analyze & Trade:**
   - If no positions: scan watchlist for entry setups
   - Check stock price action using get_ltp_data and get_candle_data (5min/15min from broker)
   - Evaluate option chain: strike selection, premium, OI, bid-ask spread
   - Calculate Greeks to assess option value (theta decay, delta exposure)
   - Always check market regime before directional trades — don't fight the trend
   - Consider expiry proximity: avoid near-expiry options with high theta decay

2. **Monitor Open Positions:**
   - Check current P&L via {"get_paper_positions" if mode == "paper" else "get_positions"}
   - Decide: HOLD / TRAIL SL / EXIT based on price action and indicators
   - If P&L is deteriorating, consider early exit rather than hoping for reversal

3. **Opportunity Scanning:**
   - Even with positions open, watch for new setups (if position count allows)
   - New opportunities can emerge any time until 14:45

4. **Decision Logging:**
   - Call log_decision after EVERY significant action (entry, exit, skip, analysis)
   - Include your reasoning — this powers the workflow visualizer

5. **State Updates:**
   After each cycle, update these session state variables:
   - daily_pnl: current realized + unrealized P&L
   - open_positions_count: number of open positions
   - monitoring_interval: seconds until next check
     - No positions, scanning: 300 (5 min)
     - Position open, in profit: 180 (3 min)
     - Position near stop-loss: 60 (1 min)
     - P&L approaching daily limit: 60 (1 min)
     - Last 30 min before square-off: 60 (1 min)
   - phase: current phase (planning / execution / monitoring)

=== TRADING PRINCIPLES ===
- Risk management is your #1 priority. Preserve capital.
- One good trade is better than five mediocre ones.
- If the market is choppy or unclear, it's OK to not trade.
- Never average down a losing position.
- Always have a stop-loss level in mind before entering.
- Check both stock and index trend before entering directional trades.
- Indian stock options are monthly expiry only. If current month expiry is within 3-4 days, consider next month to avoid theta decay.
"""
```

---

## 7. Entry Point (`main.py`)

```python
import asyncio
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from odta.agents.root_agent import build_root_agent
from odta.models.config import load_config
from odta.db.connection import get_db_connection
from odta.db.schema import initialize_database


async def main():
    load_dotenv()
    config = load_config()

    # Initialize database
    initialize_database(config.database.path)

    # Build agent tree
    root_agent = build_root_agent()

    # Setup ADK runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="odta",
        session_service=session_service,
    )

    # Create session with initial state
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).strftime("%Y-%m-%d")

    session = await session_service.create_session(
        app_name="odta",
        user_id="trader",
        state={
            "trade_date": today,
            "app:mode": config.mode,
            "app:max_daily_loss": config.guardrails.max_daily_loss,
            "app:max_open_positions": config.guardrails.max_open_positions,
            "app:square_off_time": config.guardrails.square_off_time,
            "daily_pnl": 0,
            "open_positions_count": 0,
            "monitoring_interval": 120,
            "phase": "pre_market",
        },
    )

    print(f"=== ODTA Starting | {today} | Mode: {config.mode.upper()} ===")

    # Kick off the trading day
    content = types.Content(
        role="user",
        parts=[types.Part(text=f"Begin trading day. Date: {today}. Time: {datetime.now(ist).strftime('%H:%M')} IST.")],
    )

    async for event in runner.run_async(
        user_id="trader",
        session_id=session.id,
        new_message=content,
    ):
        # Log agent events
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    print(f"[{event.author}] {part.text[:200]}")

        if event.is_final_response():
            print(f"\n=== ODTA Day Complete | Final output from: {event.author} ===")
            if event.content and event.content.parts:
                print(event.content.parts[0].text)
            break

    print(f"=== ODTA Shutdown | {today} ===")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 8. Config Model (`odta/models/config.py`)

```python
from pydantic import BaseModel
import yaml


class LLMConfig(BaseModel):
    model: str = "gemini-2.0-flash"


class DatabaseConfig(BaseModel):
    path: str = "/Users/bhaveshghodasara/Development/price-vol-pattern/data/stocks.duckdb"


class BrokerConfig(BaseModel):
    mcp_server_path: str = "./angel-one-mcp-server"


class GuardrailsConfig(BaseModel):
    max_daily_loss: int = 5000
    max_open_positions: int = 2
    square_off_time: str = "15:00"
    pre_market_start: str = "08:45"


class AppConfig(BaseModel):
    llm: LLMConfig = LLMConfig()
    database: DatabaseConfig = DatabaseConfig()
    broker: BrokerConfig = BrokerConfig()
    guardrails: GuardrailsConfig = GuardrailsConfig()
    mode: str = "paper"


def load_config(path: str = "config.yaml") -> AppConfig:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return AppConfig(**data)
    except FileNotFoundError:
        return AppConfig()  # defaults
```

---

## 9. Dashboard API Contracts

### 9.1 API Routes (Next.js)

All routes read from the same DuckDB database the agent writes to.

**`GET /api/status`**
```json
{
  "mode": "paper",
  "phase": "monitoring",
  "trade_date": "2025-01-28",
  "daily_pnl": 2025.0,
  "open_positions": 1,
  "max_positions": 2,
  "max_daily_loss": 5000,
  "agent_running": true
}
```

**`GET /api/positions`**
```json
{
  "open": [
    {
      "symbol": "TATAMOTORS",
      "option_symbol": "TATAMOTORS25JAN840CE",
      "direction": "BUY",
      "quantity": 600,
      "entry_price": 18.0,
      "current_price": 21.5,
      "unrealized_pnl": 2100,
      "entry_time": "2025-01-28T09:35:00"
    }
  ],
  "closed_today": [
    {
      "symbol": "RELIANCE",
      "option_symbol": "RELIANCE25JAN2500CE",
      "entry_price": 45.5,
      "exit_price": 62.0,
      "quantity": 250,
      "pnl": 4125,
      "entry_time": "2025-01-28T10:15:00",
      "exit_time": "2025-01-28T12:30:00"
    }
  ]
}
```

**`GET /api/workflow?date=2025-01-28`**
```json
{
  "date": "2025-01-28",
  "decisions": [
    {
      "timestamp": "2025-01-28T09:00:00",
      "phase": "pre_market",
      "action_type": "analysis",
      "symbol": null,
      "summary": "Market regime: Nifty bullish above 22000 support",
      "reasoning": "SMA_20 > SMA_50, RSI at 62, trending regime...",
      "data_points": {"nifty_close": 22150, "rsi": 62, "trend": "bullish"}
    },
    {
      "timestamp": "2025-01-28T09:05:00",
      "phase": "pre_market",
      "action_type": "stock_selection",
      "symbol": "TATAMOTORS",
      "summary": "Shortlisted: breakout above 820 with volume spike",
      "reasoning": "Volume 3x average, RSI 58, price above SMA_20..."
    }
  ]
}
```

**`GET /api/trades?date=2025-01-28`**
```json
{
  "date": "2025-01-28",
  "trades": [
    {
      "symbol": "RELIANCE",
      "option_symbol": "RELIANCE25JAN2500CE",
      "direction": "BUY_CE",
      "entry_price": 45.5,
      "exit_price": 62.0,
      "quantity": 250,
      "pnl": 4125,
      "entry_rationale": "Breakout above 2480 resistance with strong volume",
      "exit_rationale": "Target hit at 2510 level",
      "tags": "breakout,momentum"
    }
  ],
  "daily_summary": "Net P&L: +2,025. Win rate 50%. Afternoon reversal risk...",
  "total_pnl": 2025
}
```

**`GET /api/diary?date=2025-01-28`**
```json
{
  "date": "2025-01-28",
  "market_conditions": "Nifty bullish, Auto sector strong, Banking flat",
  "trades": [...],
  "learnings": "Volume confirmation on breakouts continues to be reliable",
  "mistakes": "Entered TATAMOTORS PE against broader market recovery",
  "daily_summary": "Two trades, one winner one loser. Net positive..."
}
```

### 9.2 DuckDB from Next.js

Use `duckdb-wasm` or a lightweight API layer to read DuckDB from Next.js:

```typescript
// Option A: Direct DuckDB via better-sqlite3 or duckdb-node
import duckdb from 'duckdb';

const db = new duckdb.Database('./data/trading.db', { access_mode: 'READ_ONLY' });

// Option B: FastAPI sidecar (if DuckDB node binding is problematic)
// Small Python FastAPI that reads DuckDB and serves JSON
```

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/test_risk_callbacks.py
def test_reject_when_daily_loss_exceeded():
    """Risk callback should reject orders when daily loss limit is hit."""

def test_reject_when_max_positions_reached():
    """Risk callback should reject new orders when position limit reached."""

def test_reject_after_square_off_time():
    """Risk callback should reject BUY orders after square-off time."""

def test_reject_banned_securities():
    """Risk callback should reject orders for banned stocks."""

def test_allow_valid_order():
    """Risk callback should return None for valid orders."""


# tests/test_sql_agent.py
def test_select_query_succeeds():
    """SQL agent should execute valid SELECT queries."""

def test_reject_non_select_query():
    """SQL agent should reject INSERT/UPDATE/DELETE queries."""


# tests/test_greeks.py
def test_call_greeks_calculation():
    """Greeks calculator should return valid delta/gamma/theta/vega for a call option."""

def test_put_greeks_calculation():
    """Greeks calculator should return negative delta for a put option."""

def test_implied_volatility():
    """IV calculation should converge to a reasonable value."""


# tests/test_loop_controller.py
def test_escalate_at_square_off():
    """Loop controller should escalate when time >= square_off_time."""

def test_escalate_at_max_loss():
    """Loop controller should escalate when daily_pnl <= -max_daily_loss."""

def test_continue_during_trading_hours():
    """Loop controller should not escalate during normal trading hours with P&L within limits."""
```

### 10.2 Integration Testing with `adk web`

```bash
# Start the ADK dev UI
adk web odta/agents

# In the browser:
# 1. Send "Begin trading day" to kick off pre-market
# 2. Inspect tool calls in the UI
# 3. Watch state updates in real-time
# 4. Test edge cases by modifying state manually
```

### 10.3 Paper Trading Validation

Run a full day in paper mode and verify:
- [ ] Pre-market analysis produces a watchlist
- [ ] Agent enters trades based on analysis
- [ ] Position monitoring runs at correct intervals
- [ ] Stop-loss exits work correctly
- [ ] Daily loss limit triggers hard stop
- [ ] EOD summary and diary entry are written
- [ ] Decision log captures all reasoning
- [ ] Dashboard displays all data correctly

---

## 11. Key Implementation Notes

### 11.1 ADK Version Compatibility

- `google-adk >= 0.5.0` is required
- `google_search` tool isolation is an ADK constraint — may be relaxed in future versions
- `before_tool_callback` signature: `(CallbackContext, str, dict) -> dict | None`

### 11.2 DuckDB Concurrency

DuckDB supports one writer at a time. The agent writes (trade diary, decision log) and the dashboard reads. Use `READ_ONLY` mode for the dashboard connection to avoid conflicts. If concurrent write access becomes an issue, consider:
- Write-ahead logging (WAL mode)
- Separate writer process with queue
- Switch to PostgreSQL/Supabase in Phase 2

### 11.3 MCP Server Lifecycle

The `McpToolset` with `StdioConnectionParams` launches the MCP server as a subprocess. It starts when the agent initializes and stops when the agent shuts down. Ensure:
- MCP server dependencies are installed in the submodule venv
- Environment variables are passed correctly
- Graceful shutdown on agent exit

### 11.4 Gemini API Rate Limits

With Gemini 2.0 Flash:
- Monitor RPM (requests per minute) limits
- The trading loop with 1-5 min intervals should be well within limits
- Pre-market pipeline makes 4-5 sequential LLM calls — should complete in ~30 seconds
- `google_search` is billed per search query executed

### 11.5 Error Handling

- Tool functions should always return `dict` with `status` key ("success" or "error")
- Never raise exceptions from tools — return error dicts so the LLM can reason about failures
- MCP connection failures should be caught and reported to the LLM as tool errors
- Network timeouts: set reasonable timeouts on broker API calls (10s for data, 30s for orders)
