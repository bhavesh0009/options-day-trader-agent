"""ADK entry point. Exports root_agent for `adk web` and `adk run`."""

from dotenv import load_dotenv
load_dotenv()

from odta.models.config import load_config
from odta.db.schema import initialize_database

config = load_config()
initialize_database(config.database.path)

from odta.agents.root_agent import build_root_agent

root_agent = build_root_agent()
