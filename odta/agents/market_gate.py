"""Market Gate Agent - Prevents trading loop from starting outside market hours."""

import asyncio
from datetime import datetime
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from odta.constants import (
    IST,
    MARKET_OPEN,
    MARKET_CLOSE,
    SATURDAY,
    SUNDAY,
)


class MarketGateAgent(BaseAgent):
    """Non-LLM agent that waits for market to open before allowing trading loop.

    Runs AFTER pre-market pipeline, BEFORE trading loop.
    Sleeps until market opens (9:15 AM), then allows execution to proceed.
    If market is closed or it's weekend, escalates immediately to skip trading.
    """

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        now = datetime.now(IST)
        current_time_obj = now.time()
        current_weekday = now.weekday()

        # Check 1: Weekend - Skip trading entirely
        if current_weekday in (SATURDAY, SUNDAY):
            yield Event(
                author=self.name,
                actions=EventActions(escalate=True),
                content="Weekend detected. Skipping trading session.",
            )
            return

        # Check 2: After market close - Skip trading
        if current_time_obj > MARKET_CLOSE:
            yield Event(
                author=self.name,
                actions=EventActions(escalate=True),
                content=f"Market closed (current time: {now.strftime('%H:%M')} > 15:30). Skipping trading session.",
            )
            return

        # Check 3: Before market open - Wait
        if current_time_obj < MARKET_OPEN:
            seconds_until_open = (
                datetime.combine(now.date(), MARKET_OPEN) -
                datetime.combine(now.date(), current_time_obj)
            ).total_seconds()

            yield Event(
                author=self.name,
                content=f"Market opens at 09:15. Current time: {now.strftime('%H:%M')}. "
                        f"Waiting {int(seconds_until_open)} seconds...",
            )

            # Sleep until market opens
            await asyncio.sleep(seconds_until_open)

            yield Event(
                author=self.name,
                content="Market is now open. Proceeding to trading loop.",
            )
        else:
            # Market is already open
            yield Event(
                author=self.name,
                content=f"Market is open (current time: {now.strftime('%H:%M')}). Proceeding to trading loop.",
            )
