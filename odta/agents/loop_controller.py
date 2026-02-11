import asyncio
from datetime import datetime
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from odta.constants import (
    IST,
    StateKeys,
    DEFAULT_MAX_DAILY_LOSS,
    SQUARE_OFF_TIME_STR,
    DEFAULT_MONITORING_INTERVAL,
    MARKET_OPEN,
    MARKET_CLOSE,
    SATURDAY,
    SUNDAY,
)


class LoopController(BaseAgent):
    """Non-LLM agent that checks market hours and P&L limits.

    Runs after each trader_agent iteration. Sleeps for the adaptive
    monitoring interval, then checks if the trading loop should end.
    """

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        now = datetime.now(IST)
        current_time_str = now.strftime("%H:%M")
        current_time_obj = now.time()
        current_weekday = now.weekday()

        square_off_time = ctx.session.state.get(StateKeys.APP_SQUARE_OFF_TIME, SQUARE_OFF_TIME_STR)
        daily_pnl = ctx.session.state.get(StateKeys.DAILY_PNL, 0)
        max_loss = ctx.session.state.get(StateKeys.APP_MAX_DAILY_LOSS, DEFAULT_MAX_DAILY_LOSS)

        # Check if we should stop the trading loop
        should_stop = False
        reason = None

        # Stop Reason 1: Weekend (no trading on Sat/Sun)
        if current_weekday in (SATURDAY, SUNDAY):
            should_stop = True
            reason = "weekend"

        # Stop Reason 2: Before market open (< 9:15 AM)
        elif current_time_obj < MARKET_OPEN:
            should_stop = True
            reason = "market_not_open"

        # Stop Reason 3: After market close (> 3:30 PM)
        elif current_time_obj > MARKET_CLOSE:
            should_stop = True
            reason = "market_closed"

        # Stop Reason 4: Past square-off time (>= 3:00 PM)
        elif current_time_str >= square_off_time:
            should_stop = True
            reason = "square_off_time"

        # Stop Reason 5: Daily loss limit breached
        elif daily_pnl <= -max_loss:
            should_stop = True
            reason = "max_loss_breached"

        if should_stop:
            ctx.session.state[StateKeys.STOP_REASON] = reason
            ctx.session.state[StateKeys.PHASE] = "eod"

        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_stop),
        )

        if not should_stop:
            interval = ctx.session.state.get(StateKeys.MONITORING_INTERVAL, DEFAULT_MONITORING_INTERVAL)
            await asyncio.sleep(interval)
