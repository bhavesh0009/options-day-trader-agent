# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An autonomous AI agent that day-trades stock options on the Indian NSE F&O market. Built on Google ADK (Agent Development Kit) with Gemini models, using a hierarchical agent architecture for market analysis, trading execution, and risk management.

## Key Commands

### Development Setup
```bash
# Initial setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
git submodule update --init  # Initialize Angel One MCP server

# Environment configuration
cp .env.example .env
# Edit .env with API keys (GOOGLE_API_KEY, ANGEL_ONE_*)
# Edit config.yaml with database path and preferences
```

### Database Initialization
```bash
# Initialize or migrate database schema
python -c "from odta.db.schema import initialize_database; initialize_database('path/to/stocks.duckdb')"
```

### Running the Agent
```bash
# Production run (executes full trading day)
python main.py

# Interactive debugging with ADK Web UI
adk web adk_apps

# Direct ADK run (if adk_apps/agent.py exists)
adk run adk_apps
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_sql_agent.py -v

# Run with coverage
pytest tests/ -v --cov=odta --cov-report=html
```

### Code Quality
```bash
# Format and lint
ruff check odta/
ruff format odta/
```

## Architecture Overview

The system uses a hierarchical **Google ADK agent tree** with sequential and loop agents:

### Agent Hierarchy
```
daily_session (SequentialAgent)
├── pre_market_agent (SequentialAgent)
│   ├── diary_reader → Reads trade_diary, extracts learnings
│   ├── market_scanner → Queries DuckDB, analyzes market regime
│   ├── news_agent → Google Search via Gemini grounding (isolated)
│   └── watchlist_finalizer → Consolidates to 2-5 stocks
│
├── trading_loop (LoopAgent, max 300 iterations)
│   ├── trader_agent (LlmAgent) → Primary trading brain
│   │   Tools: broker MCP, SQL, indicators, greeks, charts, diary, logger
│   │   Callback: risk_manager (blocks violations BEFORE tool execution)
│   └── loop_controller (BaseAgent) → Time check, P&L check, adaptive sleep
│
└── eod_agent (LlmAgent) → Square off positions, write diary, summary
```

### Critical Concepts

**ADK Agent Entry Points:**
- `odta/agents/agent.py` exports `root_agent` for `adk web` and `adk run` commands
- `main.py` provides full production orchestration with ADK Runner + session management
- Both initialize database via `odta.db.schema.initialize_database()`

**Broker Integration:**
- Angel One API accessed via MCP (Model Context Protocol) server
- Git submodule: `angel-one-mcp-server/`
- Connection: `McpToolset` with `StdioConnectionParams` spawning Python subprocess
- Paper mode: `DRY_RUN_MODE=true` (real data, simulated execution)
- Live mode: `DRY_RUN_MODE=false` + `mode: "live"` in config.yaml

**Risk Guardrails (Hardcoded, Non-Overridable):**
- Enforced in `odta/risk/callbacks.py` via `before_tool_callback` on trader_agent
- Blocks tool execution if: daily loss > Rs 5,000 OR open_positions > 2
- Reads session state: `daily_pnl`, `open_positions_count`
- Critical: callbacks run BEFORE broker tools, not after

**Data Flow:**
- DuckDB at `config.database.path` contains: `fno_stocks`, `ban_list`, `trade_diary`, `decision_log`, `paper_positions`
- `fno_stocks` is pre-populated with historical OHLCV (not managed by agent)
- Agent reads `fno_stocks` via `sql_agent` tool for market analysis
- Agent writes to `trade_diary` (EOD), `decision_log` (throughout), `paper_positions` (paper mode only)

## Code Structure

**odta/agents/**: ADK agent definitions
- `root_agent.py` - Builds agent tree hierarchy
- `pre_market.py` - Sequential pre-market analysis (diary, scanner, news, watchlist)
- `trader.py` - Main LlmAgent with all tools + risk callback
- `loop_controller.py` - BaseAgent for time/P&L checks, adaptive sleep logic
- `eod.py` - End-of-day square off and diary writing
- `news.py` - Isolated LlmAgent for Google Search (ADK limitation: search must be in separate agent)

**odta/tools/**: Native Python tools (not MCP)
- `sql_agent.py` - Natural language → SQL → DuckDB query execution
- `indicators.py` - pandas-ta wrapper for technical indicators
- `greeks.py` - Option pricing (Black-Scholes, greeks calculation)
- `charts.py` - mplfinance + Gemini Vision for chart analysis
- `trade_diary.py` - Read/write trade_diary table
- `decision_logger.py` - Log all agent decisions to decision_log table
- `paper_tracker.py` - Track simulated positions in paper mode
- `market_sentiment.py` - Sentiment analysis utilities

**odta/risk/**: Risk management
- `callbacks.py` - `before_tool_callback` function for trader_agent (blocks violations)

**odta/prompts/**: System prompts (dynamic instruction functions)
- Return strings that get injected into agent `instruction` parameter
- Access session state via closure over `config`

**odta/db/**: Database layer
- `schema.py` - DDL for sequences and tables, migration logic
- Uses DuckDB sequences for auto-increment IDs

**odta/models/**: Pydantic models
- `config.py` - AppConfig, GuardrailsConfig, etc. (loaded from config.yaml)
- `trade.py` - Trade, Position models

**odta/utils/**: Utilities
- `time_helpers.py` - IST timezone, market hours checks
- `logger.py` - Structured logging setup
- `json_helpers.py` - JSON serialization utilities

## Important Patterns

**Session State Management:**
- ADK sessions store: `trade_date`, `daily_pnl`, `open_positions_count`, `phase`, `monitoring_interval`
- Updated by agents via `ctx.update_state()` or `state["key"] = value`
- Risk callbacks read state to enforce guardrails
- Loop controller reads state to determine sleep duration

**Tool Callback Pattern:**
```python
# In trader.py
from odta.risk.callbacks import risk_manager

trader = LlmAgent(
    name="trader_agent",
    tools=[...],
    before_tool_callback=risk_manager,  # Runs BEFORE tool execution
)
```

**SQL Agent Tool:**
- Agent calls `sql_agent(question="...")` with natural language
- Tool converts to SQL, executes on DuckDB, returns results
- Understands schema: `fno_stocks`, `ban_list`, `trade_diary`, etc.
- Used heavily in pre_market_agent for market analysis

**Chart Analysis:**
- `charts.generate_chart()` creates mplfinance chart, saves to /tmp
- Returns base64-encoded PNG
- Agent can pass to Gemini Vision for analysis (multimodal)

**Paper Mode vs Live Mode:**
- Config: `mode: "paper"` or `mode: "live"`
- Paper: MCP server runs with `DRY_RUN_MODE=true`, writes to `paper_positions` table
- Live: MCP server executes real orders via Angel One API
- Risk guardrails active in both modes

## Testing Patterns

Tests use pytest with fixtures for:
- Mock DuckDB connections
- Mock ADK agent contexts
- Sample market data

Test files mirror source structure:
- `tests/test_sql_agent.py` → `odta/tools/sql_agent.py`
- `tests/test_risk_callbacks.py` → `odta/risk/callbacks.py`

## Configuration Files

**config.yaml** (user-editable):
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
  pre_market_start: "08:45"
mode: "paper"  # or "live"
```

**.env** (secrets, never commit):
- `GOOGLE_API_KEY` - Gemini API key
- `ANGEL_ONE_*` - Broker credentials (used by MCP server subprocess)
- `DRY_RUN_MODE` - "true" for paper, "false" for live (also set in config.yaml mode)

## Common Gotchas

1. **Database must exist before running**: The agent does NOT create `fno_stocks` table or populate historical data. Only creates `trade_diary`, `decision_log`, `paper_positions`, `ban_list`.

2. **MCP server as git submodule**: Changes to Angel One MCP server code require committing in submodule repo, then updating parent repo reference.

3. **ADK isolation for Google Search**: Due to ADK limitations, the `news_agent` must be a separate agent from `market_scanner` to use Google Search grounding.

4. **Risk callbacks are synchronous**: The `before_tool_callback` runs in agent event loop, cannot use async/await.

5. **Loop controller logic**: Must return control to LoopAgent by NOT calling any tools itself. Only updates state and returns text.

6. **Chart paths in /tmp**: Generated charts are temporary files, clean up after analysis.

7. **Session state keys**: Use namespaced keys like `app:mode` for config values to avoid collisions with agent state.

## ADK-Specific Constraints

- **Agent types**: SequentialAgent (linear), LoopAgent (repeating), LlmAgent (reasoning), BaseAgent (custom logic)
- **Tool visibility**: Tools declared on an agent are only available to that agent, not children
- **State scope**: Session state is shared across all agents in the tree
- **MCP toolsets**: Connected via stdio subprocess, must specify `cwd` and `env` correctly
- **Prompt engineering**: Use `instruction` parameter (static) and `dynamic_instruction_fn` (state-dependent)

## Dependencies

Key libraries:
- `google-adk` - Agent orchestration framework
- `google-genai` - Gemini API client
- `duckdb` - Embedded analytical database
- `pandas-ta` - Technical analysis indicators
- `mplfinance` - Financial charting
- `pydantic` - Configuration validation
- `mcp` - Model Context Protocol for tool servers

## Documentation

- [PRD](docs/PRD.md) - Product requirements
- [Technical Implementation](docs/TECHNICAL_IMPLEMENTATION.md) - Architecture details
- [Progress](docs/PROGRESS.md) - Development status
