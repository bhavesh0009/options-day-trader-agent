"""
ODTA Trader Agent - ADK entry point.

This module serves as the ADK web interface entry point,
importing the fully configured root_agent from the main package.
"""

from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Import the root_agent from the main package
from odta.agents.agent import root_agent

# Export for ADK web
__all__ = ["root_agent"]
