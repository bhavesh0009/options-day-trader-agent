import os

from google.adk.agents import SequentialAgent, LoopAgent
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
                    "MAX_ORDER_QUANTITY": str(
                        config.guardrails.max_open_positions
                    ),
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

    # Trading loop: trader reasons -> loop_controller checks time & sleeps -> repeat
    trading_loop = LoopAgent(
        name="trading_loop",
        sub_agents=[trader, loop_ctrl],
        max_iterations=300,  # safety cap (~10 hours at 2min avg)
    )

    return SequentialAgent(
        name="daily_session",
        sub_agents=[pre_market, trading_loop, eod],
    )
