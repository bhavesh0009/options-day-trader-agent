from google.adk.agents import LlmAgent
from google.adk.tools import google_search

from odta.prompts.news import NEWS_INSTRUCTION


def build_news_agent(config):
    return LlmAgent(
        model=config.llm.model,
        name="news_analyst",
        instruction=NEWS_INSTRUCTION,
        tools=[google_search],
        output_key="news_analysis",
    )
