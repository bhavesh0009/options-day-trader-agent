# Options Day Trader Agent (ODTA)

An autonomous AI agent that day-trades stock options on the Indian NSE F&O market. Built on [Google ADK](https://google.github.io/adk-docs/) with Gemini, it analyzes markets pre-open, selects high-conviction stocks, executes option trades, monitors positions in real-time, and squares off before market close.

## Architecture

```
root_agent (SequentialAgent: "daily_session")
│
├── pre_market_agent (SequentialAgent)
│     ├── diary_reader (LlmAgent)      → reads past trades, outputs learnings
│     ├── market_scanner (LlmAgent)    → queries DB, analyzes regime, shortlists
│     ├── news_agent (LlmAgent)        → Google Search (isolated, ADK limitation)
│     └── watchlist_finalizer (LlmAgent) → consolidates into 2-5 stocks
│
├── trading_loop (LoopAgent)
│     ├── trader_agent (LlmAgent)      → all tools, primary trading brain
│     │     before_tool_callback: risk_manager
│     └── loop_controller (BaseAgent)  → time/P&L check, adaptive sleep
│
└── eod_agent (LlmAgent)              → square off, diary write, summary
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | Google ADK |
| LLM | Configurable (any ADK-compatible model) |
| Broker | Angel One via MCP Server |
| Database | DuckDB |
| Indicators | pandas-ta |
| Charts | mplfinance + Gemini Vision |
| News | Gemini Google Search Grounding |
| Dashboard | Next.js (Phase 1d) |

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd options-day-trader-agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Setup Angel One MCP Server

```bash
git submodule add https://github.com/bhavesh0009/angel-one-mcp-server.git
git submodule update --init
```

### 4. Configure

Edit `config.yaml`:

```yaml
llm:
  model: "gemini-3-pro-preview"  # Or any ADK-compatible model
database:
  path: "/path/to/stocks.duckdb"
broker:
  mcp_server_path: "./angel-one-mcp-server"
guardrails:
  max_daily_loss: 5000
  max_open_positions: 2
  square_off_time: "15:00"
mode: "paper"   # paper | live
```

### 5. Initialize database

```bash
python -c "from odta.db.schema import initialize_database; initialize_database('path/to/stocks.duckdb')"
```

## Usage

### Run the agent

```bash
python main.py
```

### Interactive debugging with ADK Web UI

```bash
adk web adk_apps
```

### Run tests

```bash
pytest tests/ -v
```

## Project Structure

```
odta/
├── agents/          # ADK agent definitions (root, trader, pre_market, news, eod, loop_controller)
├── tools/           # Native Python tools (sql, greeks, indicators, charts, sentiment, diary, logger)
├── risk/            # Risk manager callback (before_tool_callback)
├── prompts/         # System prompts (dynamic instruction functions)
├── db/              # DuckDB connection + schema
├── models/          # Pydantic models (config, trade)
└── utils/           # Time helpers, logging
```

## Risk Guardrails (Hardcoded, Non-Overridable)

| Rule | Value |
|------|-------|
| Max daily loss | Rs 5,000 |
| Max open positions | 2 |
| Square off time | 3:00 PM IST |
| Banned securities | Enforced |

## Angel One Integration

The broker API is integrated via the [Angel One MCP Server](https://github.com/bhavesh0009/angel-one-mcp-server) as a git submodule. ADK connects to it using `McpToolset` with `StdioConnectionParams`:

- **Paper mode**: MCP server runs with `DRY_RUN_MODE=true` — real market data, simulated execution
- **Live mode**: Set `DRY_RUN_MODE=false` and `mode: "live"` in config

Available MCP tools: `place_order`, `modify_order`, `cancel_order`, `get_positions`, `get_order_book`, `get_ltp_data`, `get_candle_data`, `get_option_greek`, `search_scrip`, and more.

## Documentation

- [Product Requirements (PRD)](docs/PRD.md)
- [Technical Implementation](docs/TECHNICAL_IMPLEMENTATION.md)
