import asyncio
import os
from datetime import datetime

import pytz
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from odta.agents.root_agent import build_root_agent
from odta.models.config import load_config
from odta.db.schema import initialize_database
from odta.utils.logger import setup_logger


async def main():
    load_dotenv()
    config = load_config()

    # Setup logger with timestamped log file
    ist = pytz.timezone("Asia/Kolkata")
    timestamp = datetime.now(ist).strftime("%Y-%m-%d_%H%M%S")
    log_file = f"logs/run_{timestamp}.log"
    logger = setup_logger(log_file=log_file)

    print(f"{'='*80}")
    print(f"ODTA Session Started: {datetime.now(ist).strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"Log File: {log_file}")
    print(f"Mode: {config.mode.upper()}")
    print(f"{'='*80}\n")

    # Initialize database (create new tables if needed)
    initialize_database(config.database.path)
    logger.info(f"Database initialized: {config.database.path}")

    # Build agent tree
    root_agent = build_root_agent()
    logger.info("Agent tree built successfully")

    # Setup ADK runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="odta",
        session_service=session_service,
    )

    # Create session with initial state
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).strftime("%Y-%m-%d")

    session = await session_service.create_session(
        app_name="odta",
        user_id="trader",
        state={
            "trade_date": today,
            "app:mode": config.mode,
            "app:max_daily_loss": config.guardrails.max_daily_loss,
            "app:max_open_positions": config.guardrails.max_open_positions,
            "app:square_off_time": config.guardrails.square_off_time,
            "daily_pnl": 0,
            "open_positions_count": 0,
            "monitoring_interval": 120,
            "phase": "pre_market",
        },
    )

    print(f"=== ODTA Starting | {today} | Mode: {config.mode.upper()} ===")
    logger.info(f"Session created: {session.id} | Mode: {config.mode}")

    # Kick off the trading day
    content = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"Begin trading day. Date: {today}. Time: {datetime.now(ist).strftime('%H:%M')} IST."
            )
        ],
    )

    async for event in runner.run_async(
        user_id="trader",
        session_id=session.id,
        new_message=content,
    ):
        # Debug: log all events
        logger.debug(f"Event: author={event.author}, is_final={event.is_final_response()}, has_content={bool(event.content)}")

        # Log all agent outputs
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    full_text = part.text
                    # Print full text to console
                    print(f"\n{'='*80}\n[{event.author}]\n{'='*80}")
                    print(full_text)
                    print('='*80 + '\n')
                    # Log truncated version to file (to avoid huge log files)
                    logger.info(f"[{event.author}] {full_text[:500]}...")

        # Only break when the root agent (daily_session) completes
        # Not when individual sub-agents finish
        if event.is_final_response():
            if event.author == "daily_session":
                print(f"\n=== ODTA Day Complete | Final output from: {event.author} ===")
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text
                    print(final_text)
                    logger.info(f"Final: {final_text[:500]}")
                break
            else:
                logger.info(f"Sub-agent {event.author} completed, continuing to next agent...")

    print(f"=== ODTA Shutdown | {today} ===")
    logger.info("ODTA shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
