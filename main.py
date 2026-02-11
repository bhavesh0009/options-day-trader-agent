import asyncio
import os
from datetime import datetime

from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from odta.agents.root_agent import build_root_agent
from odta.models.config import load_config
from odta.db.schema import initialize_database
from odta.utils.logger import setup_logger
from odta.constants import IST, StateKeys, DEFAULT_MONITORING_INTERVAL


async def main():
    load_dotenv()
    config = load_config()

    # Setup logger with timestamped log file
    timestamp = datetime.now(IST).strftime("%Y-%m-%d_%H%M%S")
    log_file = f"logs/run_{timestamp}.log"
    logger = setup_logger(log_file=log_file)

    print(f"{'='*80}")
    print(f"ODTA Session Started: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}")
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
    today = datetime.now(IST).strftime("%Y-%m-%d")

    session = await session_service.create_session(
        app_name="odta",
        user_id="trader",
        state={
            StateKeys.TRADE_DATE: today,
            StateKeys.APP_MODE: config.mode,
            StateKeys.APP_MAX_DAILY_LOSS: config.guardrails.max_daily_loss,
            StateKeys.APP_MAX_OPEN_POSITIONS: config.guardrails.max_open_positions,
            StateKeys.APP_SQUARE_OFF_TIME: config.guardrails.square_off_time,
            StateKeys.DAILY_PNL: 0,
            StateKeys.OPEN_POSITIONS_COUNT: 0,
            StateKeys.MONITORING_INTERVAL: DEFAULT_MONITORING_INTERVAL,
            StateKeys.PHASE: "pre_market",
        },
    )

    print(f"=== ODTA Starting | {today} | Mode: {config.mode.upper()} ===")
    logger.info(f"Session created: {session.id} | Mode: {config.mode}")

    # Kick off the trading day
    content = types.Content(
        role="user",
        parts=[
            types.Part(
                text=f"Begin trading day. Date: {today}. Time: {datetime.now(IST).strftime('%H:%M')} IST."
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
                    # Log full text to file for complete audit trail
                    logger.info(f"[{event.author}] {full_text}")

        # Only break when the root agent (daily_session) completes
        # Not when individual sub-agents finish
        if event.is_final_response():
            if event.author == "daily_session":
                print(f"\n=== ODTA Day Complete | Final output from: {event.author} ===")
                if event.content and event.content.parts:
                    final_text = event.content.parts[0].text
                    print(final_text)
                    logger.info(f"Final: {final_text}")
                break
            else:
                logger.info(f"Sub-agent {event.author} completed, continuing to next agent...")

    print(f"=== ODTA Shutdown | {today} ===")
    logger.info("ODTA shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
