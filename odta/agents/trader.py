from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool

from odta.tools.sql_agent import query_database
from odta.tools.greeks import calculate_greeks
from odta.tools.indicators import calculate_indicator
from odta.tools.market_sentiment import get_market_regime, get_sector_sentiment
from odta.tools.trade_diary import read_trade_diary, write_trade_diary
from odta.tools.decision_logger import log_decision
from odta.tools.charts import generate_chart, generate_index_chart
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
        generate_chart,
        generate_index_chart,
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
