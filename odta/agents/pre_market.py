from google.adk.agents import SequentialAgent, LlmAgent

from odta.tools.sql_agent import query_database
from odta.tools.trade_diary import read_trade_diary
from odta.tools.indicators import calculate_indicator
from odta.tools.market_sentiment import get_market_regime, get_sector_sentiment
from odta.tools.charts import generate_chart, generate_index_chart
from odta.agents.news import build_news_agent
from odta.prompts.pre_market import (
    DIARY_READER_INSTRUCTION,
    SCANNER_INSTRUCTION,
    FINALIZER_INSTRUCTION,
)


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
        tools=[
            query_database, calculate_indicator, get_market_regime,
            get_sector_sentiment, generate_chart, generate_index_chart,
        ],
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
