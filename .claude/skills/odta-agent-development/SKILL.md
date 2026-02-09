---
name: odta-agent-development
description: Develops and maintains the Options Day Trader Agent (ODTA) - an autonomous AI trading system for Indian NSE F&O markets built with Google ADK, DuckDB, and Angel One API. Use when implementing agent features, debugging trading logic, adding tools, modifying agent hierarchy, or working with MCP broker integration. Expert in ADK agent patterns, risk callbacks, session state management, and paper trading simulation.
---

# ODTA Agent Development

Expert developer skill for the Options Day Trader Agent - an autonomous AI system that day-trades stock options on Indian NSE F&O markets.

## Quick context

This is a **production-ready autonomous trading agent** built with:
- **Google ADK** (Agent Development Kit) - hierarchical agent orchestration
- **DuckDB** - analytical database with historical OHLCV data
- **Angel One MCP Server** - broker API integration via Model Context Protocol
- **Paper trading mode** - real market data, simulated execution

**Critical safety**: Hardcoded risk guardrails (max loss Rs 5,000, max 2 positions, square-off at 3 PM IST) enforced via `before_tool_callback` that blocks violations BEFORE execution.

## Essential files

**Always read first when working on this codebase:**
- [CLAUDE.md](../../CLAUDE.md) - Commands, architecture, patterns, gotchas
- [docs/PRD.md](../../docs/PRD.md) - Product requirements and workflows
- [docs/TECHNICAL_IMPLEMENTATION.md](../../docs/TECHNICAL_IMPLEMENTATION.md) - Implementation details

**Configuration:**
- `config.yaml` - Runtime config (mode, database path, guardrails)
- `.env` - API keys and credentials (never commit)

**Entry points:**
- `main.py` - Production orchestration with ADK Runner
- `odta/agents/agent.py` - ADK entry for `adk web` and `adk run`

## Core architecture

The system uses a **hierarchical ADK agent tree**:

```
daily_session (SequentialAgent)
├── pre_market_agent (SequentialAgent)
│   ├── diary_reader → Reads trade_diary for learnings
│   ├── market_scanner → SQL queries, market regime analysis
│   ├── news_agent → Google Search (isolated, ADK limitation)
│   └── watchlist_finalizer → Consolidates to 2-5 stocks
│
├── trading_loop (LoopAgent, max 300 iterations)
│   ├── trader_agent (LlmAgent) → Primary trading brain
│   │   ├── Tools: broker MCP + native Python tools
│   │   └── Callback: risk_manager (blocks violations)
│   └── loop_controller (BaseAgent) → Time/P&L check, sleep
│
└── eod_agent (LlmAgent) → Square off, diary write, summary
```

**Key insight**: `trader_agent` is the ONLY agent with full tool access. Other agents have specific, limited toolsets. This prevents context loss and maintains decision continuity.

## Development workflows

### Adding a new tool

Copy this checklist:

```
Tool Development Progress:
- [ ] Step 1: Define tool function with proper docstring
- [ ] Step 2: Add tool to appropriate agent's tool list
- [ ] Step 3: Test tool in isolation (unit test)
- [ ] Step 4: Test with adk web for integration
- [ ] Step 5: Update CLAUDE.md if tool changes workflow
```

**Step 1: Define tool function**

Location: `odta/tools/your_tool.py`

Template:
```python
def your_tool_name(param1: str, param2: int) -> dict:
    """Brief description of what this tool does.

    Longer explanation of when to use this tool and what it accomplishes.
    Include context about trading workflow if relevant.

    Args:
        param1: Description of parameter
        param2: Description of parameter

    Returns:
        dict with status and relevant data
    """
    try:
        # Implementation
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
```

**NEVER raise exceptions** - always return error dicts so LLM can reason about failures.

**Step 2: Add to agent**

Edit `odta/agents/trader.py` (or appropriate agent):
```python
from odta.tools.your_tool import your_tool_name

native_tools = [
    # ... existing tools
    your_tool_name,
]
```

**Step 3: Unit test**

Create `tests/test_your_tool.py`:
```python
def test_your_tool_success():
    """Tool should return success dict for valid inputs."""
    result = your_tool_name("valid", 42)
    assert result["status"] == "success"

def test_your_tool_error_handling():
    """Tool should return error dict, not raise exception."""
    result = your_tool_name("invalid", -1)
    assert result["status"] == "error"
    assert "reason" in result
```

**Step 4: Integration test**

```bash
# Start ADK web UI
adk web adk_apps

# In browser, manually invoke the tool and verify behavior
# Check that agent can discover and use the tool correctly
```

**Step 5: Documentation**

Update CLAUDE.md section "odta/tools/" if the tool introduces new patterns or changes existing workflows.

### Modifying agent hierarchy

Copy this checklist:

```
Agent Modification Progress:
- [ ] Step 1: Read current agent definition
- [ ] Step 2: Understand state flow and output_key usage
- [ ] Step 3: Make changes preserving state contracts
- [ ] Step 4: Test with adk web
- [ ] Step 5: Verify state updates propagate correctly
```

**Critical**: ADK session state is shared across ALL agents. Changes to one agent's state updates affect downstream agents.

**State keys convention:**
- `app:*` - Application config (read-only): `app:mode`, `app:max_daily_loss`
- Agent outputs - Written via `output_key`: `diary_context`, `watchlist`, `news_analysis`
- Runtime state - Updated by trader: `daily_pnl`, `open_positions_count`, `phase`, `monitoring_interval`

**Before modifying an agent:**
1. Check what state keys it reads: `context.state.get("key")`
2. Check what it writes: `output_key` parameter or `state["key"] = value`
3. Verify downstream agents expect this contract

**Example - Pre-market agent dependencies:**
```
diary_reader (output_key="diary_context")
    ↓
market_scanner reads state["diary_context"]
           writes state["watchlist_candidates"]
    ↓
news_agent reads state["watchlist_candidates"]
       writes state["news_analysis"]
    ↓
watchlist_finalizer reads both, writes state["watchlist"]
```

Breaking any link breaks the pipeline.

### Adding risk guardrail

Edit `odta/risk/callbacks.py` in the `risk_manager_callback` function.

**Pattern:**
```python
def risk_manager_callback(callback_context, tool_name, tool_args):
    # ... existing checks ...

    # New rule: Check your condition
    if tool_name in ORDER_TOOLS:
        if your_violation_condition:
            return {
                "status": "REJECTED",
                "reason": "Clear explanation why this is blocked"
            }

    return None  # Allow if all checks pass
```

**Test pattern:**
```python
# tests/test_risk_callbacks.py
def test_new_guardrail_blocks_violation():
    """Risk callback should reject when new rule violated."""
    # Setup mock context with violating state
    # Call risk_manager_callback
    # Assert rejection dict returned

def test_new_guardrail_allows_valid():
    """Risk callback should allow when rule satisfied."""
    # Setup mock context with valid state
    # Call risk_manager_callback
    # Assert None returned (allow)
```

**Remember**: Risk callbacks run BEFORE tool execution. Agent sees rejection as tool result and can adapt.

### Debugging agent behavior

Copy this checklist:

```
Debug Progress:
- [ ] Step 1: Reproduce issue with adk web
- [ ] Step 2: Check session state at failure point
- [ ] Step 3: Review decision_log table for reasoning
- [ ] Step 4: Verify tool results were as expected
- [ ] Step 5: Check dynamic instructions injected correctly
```

**Step 1: Reproduce with adk web**

```bash
adk web adk_apps

# In browser:
# - Set initial state to match issue scenario
# - Send user message that triggers the issue
# - Observe tool calls and responses in UI
```

**Step 2: Check session state**

In ADK web UI, inspect state panel. Verify:
- Are config values correct? (`app:mode`, `app:max_daily_loss`)
- Is runtime state accurate? (`daily_pnl`, `open_positions_count`)
- Did upstream agents write expected outputs? (`watchlist`, `news_analysis`)

**Step 3: Review decision log**

```python
# In Python console or Jupyter
import duckdb
conn = duckdb.connect("path/to/stocks.duckdb")

# Get recent decisions
conn.execute("""
    SELECT timestamp, phase, action_type, symbol, summary, reasoning
    FROM decision_log
    WHERE trade_date = '2026-02-08'
    ORDER BY timestamp DESC
    LIMIT 20
""").df()
```

This shows the agent's reasoning chain.

**Step 4: Verify tool results**

Check if tools returned expected data:
- Did `query_database` return correct rows?
- Did MCP broker tools succeed or fail?
- Are error messages clear enough for agent to understand?

**Step 5: Check dynamic instructions**

Agent instructions are functions that inject state. Verify by adding logging:

```python
# In odta/prompts/trader.py
def trader_instruction(context):
    state = context.state
    instruction = f"""You are an expert trader...

    Current P&L: Rs {state.get("daily_pnl", 0)}
    ...
    """
    print(f"[DEBUG] Trader instruction at {datetime.now()}")
    print(instruction[:200])  # Print first 200 chars
    return instruction
```

### Testing paper trading mode

```bash
# Ensure .env has DRY_RUN_MODE=true
# config.yaml has mode: "paper"

# Run full day simulation
python main.py

# Monitor in separate terminal
tail -f logs/$(date +%Y-%m-%d).log
```

**Validation checklist:**
- [ ] Pre-market produces watchlist (check state)
- [ ] Agent enters trades (check `paper_positions` table)
- [ ] Position monitoring runs at correct intervals (check logs)
- [ ] Stop-loss logic works (manually set adverse price via mock)
- [ ] Daily loss limit triggers hard stop (set `daily_pnl` to -5000 in state)
- [ ] EOD summary written to `trade_diary` (query table)
- [ ] Decision log captures reasoning (query `decision_log`)

**Query paper positions:**
```python
import duckdb
conn = duckdb.connect("path/to/stocks.duckdb")

conn.execute("""
    SELECT symbol, option_symbol, transaction_type,
           entry_price, exit_price, status, pnl
    FROM paper_positions
    WHERE trade_date = CURRENT_DATE
""").df()
```

## Critical patterns

### 1. Tool callback pattern (Risk management)

```python
# trader_agent has before_tool_callback
trader = LlmAgent(
    name="trader",
    tools=[broker_tools] + native_tools,
    before_tool_callback=risk_manager_callback,  # ← Runs BEFORE tool
)

# Callback signature
def risk_manager_callback(ctx, tool_name, tool_args) -> dict | None:
    # Return None → allow tool execution
    # Return dict → block and return dict as tool result
```

**Use case**: Enforce non-negotiable safety rules (loss limit, position count, banned stocks).

### 2. Dynamic instruction pattern (State-aware prompts)

```python
# Instruction is a FUNCTION, not a string
def trader_instruction(context: ReadonlyContext) -> str:
    state = context.state
    return f"""You are a trader.

    Current P&L: Rs {state.get("daily_pnl", 0)}
    Phase: {state.get("phase", "trading")}
    ...
    """

trader = LlmAgent(
    instruction=trader_instruction,  # ← Function, not string
)
```

Agent sees live state on every invocation without explicit tool calls.

### 3. Loop controller pattern (Non-LLM agent)

```python
class LoopController(BaseAgent):
    async def _run_async_impl(self, ctx):
        # Check conditions
        should_stop = (current_time >= square_off_time)

        # Escalate to exit loop
        yield Event(actions=EventActions(escalate=should_stop))

        # Adaptive sleep
        interval = ctx.session.state.get("monitoring_interval", 120)
        await asyncio.sleep(interval)
```

**Use case**: Time checks, adaptive sleep, P&L monitoring without burning LLM calls.

### 4. MCP toolset pattern (Broker integration)

```python
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

broker_tools = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="python",
            args=["-m", "angel_one_mcp.server"],
            cwd=os.path.abspath("./angel-one-mcp-server"),
            env={
                **os.environ,
                "DRY_RUN_MODE": "true" if paper else "false",
            }
        )
    )
)
```

Spawns MCP server as subprocess. Server lifetime tied to agent lifetime.

### 5. News agent isolation (ADK limitation)

```python
# google_search cannot coexist with other tools in same LlmAgent
news_agent = LlmAgent(
    name="news_analyst",
    tools=[google_search],  # ← Only google_search
    output_key="news_analysis",
)

# Wrap as tool for trader_agent to invoke mid-day
news_tool = AgentTool(agent=news_agent)
trader = LlmAgent(
    tools=[broker_tools] + native_tools + [news_tool],
)
```

News agent is isolated in pre-market pipeline AND available as tool for trader.

## Common tasks

### Update database schema

Edit `odta/db/schema.py` and add to `NEW_TABLES_DDL` or `SCHEMA_MIGRATIONS`:

```python
SCHEMA_MIGRATIONS = [
    # ... existing migrations
    "ALTER TABLE fno_stocks ADD COLUMN IF NOT EXISTS your_column VARCHAR",
]
```

Run:
```python
from odta.db.schema import initialize_database
initialize_database("path/to/stocks.duckdb")
```

### Test a tool in isolation

```python
# Quick test without full agent setup
from odta.tools.indicators import calculate_indicator

result = calculate_indicator(
    symbol="RELIANCE",
    indicator="RSI",
    period=14,
    lookback_days=100
)

print(result)
# Verify: result["status"] == "success"
# Check: result["values"] has recent data
```

### Query trade diary for debugging

```python
import duckdb
conn = duckdb.connect("path/to/stocks.duckdb")

# Recent trades
conn.execute("""
    SELECT trade_date, symbol, direction, entry_price, exit_price, pnl,
           entry_rationale, exit_rationale, learnings
    FROM trade_diary
    ORDER BY trade_date DESC, entry_time DESC
    LIMIT 10
""").df()

# Daily summaries
conn.execute("""
    SELECT DISTINCT trade_date, daily_summary, market_conditions
    FROM trade_diary
    WHERE daily_summary IS NOT NULL
    ORDER BY trade_date DESC
    LIMIT 5
""").df()
```

### Modify monitoring interval logic

Edit `odta/prompts/trader.py` in the instruction string:

```python
def trader_instruction(context):
    return f"""...

    5. **State Updates:**
       After each cycle, update monitoring_interval:
       - No positions, scanning: 300 (5 min)
       - Position open, in profit: 180 (3 min)
       - Position near SL: 60 (1 min)
       - YOUR NEW CONDITION: value (seconds)
    """
```

Agent reads this and updates `state["monitoring_interval"]`. Loop controller uses this value for sleep.

## Anti-patterns to avoid

### ❌ Don't bypass risk callbacks

```python
# WRONG - trying to modify callback to allow violations
if tool_name == "place_order" and state.get("emergency_override"):
    return None  # Allow despite violations
```

Risk guardrails are **non-negotiable**. No override mechanism should exist.

### ❌ Don't share tools incorrectly

```python
# WRONG - giving broker tools to pre-market agents
pre_market_scanner = LlmAgent(
    tools=[broker_tools, query_database],  # ← Should not have broker_tools
)
```

Broker tools should ONLY be on `trader_agent`. Pre-market uses database only.

### ❌ Don't forget paper mode tracking

```python
# WRONG - using live get_positions in paper mode
if config.mode == "paper":
    # Must use get_paper_positions instead
    result = get_paper_positions(tool_context)
else:
    result = broker_tools.get_positions()
```

Always check mode and use appropriate position tracker.

### ❌ Don't hardcode database paths

```python
# WRONG
conn = duckdb.connect("/Users/bhaveshghodasara/Development/...")

# RIGHT
from odta.db.connection import get_db_connection
conn = get_db_connection()  # Uses config.yaml path
```

### ❌ Don't use blocking sleep in agents

```python
# WRONG - blocks event loop
import time
time.sleep(60)

# RIGHT - async sleep in loop_controller
await asyncio.sleep(interval)
```

## Testing commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_risk_callbacks.py -v

# Run with coverage
pytest tests/ --cov=odta --cov-report=html

# Interactive debugging with ADK
adk web adk_apps

# Production run (paper mode)
python main.py

# Check database
python -c "from odta.db.schema import initialize_database; initialize_database('path/to/stocks.duckdb')"
```

## Code quality

```bash
# Lint and format
ruff check odta/
ruff format odta/

# Type checking (if using mypy)
mypy odta/
```

## Tech stack reference

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Orchestration | Google ADK | Agent hierarchy, tools, state, MCP |
| LLM | Configurable | Any ADK-compatible (Gemini, Claude, etc.) |
| Database | DuckDB | Analytical queries on OHLCV data |
| Broker | Angel One | MCP server for order execution |
| Indicators | pandas-ta | Technical analysis (RSI, MACD, etc.) |
| Charts | mplfinance | Candlestick charts + Gemini Vision |
| Testing | pytest | Unit and integration tests |
| Linting | ruff | Code quality and formatting |

## Key terminology

- **Agent tree** - Hierarchical composition of SequentialAgent, LoopAgent, LlmAgent
- **Session state** - Shared dict across all agents (`context.state`)
- **output_key** - Agent writes result to `state[output_key]`
- **before_tool_callback** - Middleware that runs before tool execution
- **MCP toolset** - Model Context Protocol server connection
- **Paper mode** - `DRY_RUN_MODE=true`, simulated execution
- **Guardrails** - Hardcoded risk limits (non-overridable)
- **Loop controller** - Non-LLM agent for time/P&L checks
- **Dynamic instruction** - Instruction function that injects live state

## Getting help

1. **Architecture questions**: Read [CLAUDE.md](../../CLAUDE.md) first
2. **Product requirements**: See [docs/PRD.md](../../docs/PRD.md)
3. **Implementation details**: See [docs/TECHNICAL_IMPLEMENTATION.md](../../docs/TECHNICAL_IMPLEMENTATION.md)
4. **ADK documentation**: https://google.github.io/adk-docs/
5. **Agent patterns**: Check existing agents in `odta/agents/`
6. **Tool patterns**: Check existing tools in `odta/tools/`

## When to use this skill

Invoke this skill when:
- Implementing new agent features or tools
- Debugging trading logic or agent behavior
- Modifying agent hierarchy or tool composition
- Adding risk guardrails or validation
- Setting up development environment
- Understanding ADK patterns and session state
- Working with MCP broker integration
- Testing paper trading simulation
- Querying trade history or decision logs
- Questions about "how does X work in ODTA"
- Need to understand agent orchestration flow

This skill provides deep expertise in the ODTA codebase, ADK agent development patterns, and autonomous trading system architecture.
