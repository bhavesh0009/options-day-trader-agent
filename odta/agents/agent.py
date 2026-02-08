"""ADK entry point. Exports root_agent for `adk web` and `adk run`."""

from odta.agents.root_agent import build_root_agent

root_agent = build_root_agent()
