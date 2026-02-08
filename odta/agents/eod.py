from google.adk.agents import LlmAgent

from odta.tools.trade_diary import write_trade_diary
from odta.tools.decision_logger import log_decision
from odta.prompts.eod import EOD_INSTRUCTION


def build_eod_agent(config):
    return LlmAgent(
        model=config.llm.model,
        name="eod_agent",
        instruction=EOD_INSTRUCTION,
        tools=[write_trade_diary, log_decision],
        output_key="daily_summary",
    )
