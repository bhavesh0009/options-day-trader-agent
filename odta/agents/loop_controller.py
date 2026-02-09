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
)


class LoopController(BaseAgent):
    """Non-LLM agent that checks market hours and P&L limits.

    Runs after each trader_agent iteration. Sleeps for the adaptive
    monitoring interval, then checks if the trading loop should end.
    """

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        now = datetime.now(IST)
        current_time = now.strftime("%H:%M")

        square_off_time = ctx.session.state.get(StateKeys.APP_SQUARE_OFF_TIME, SQUARE_OFF_TIME_STR)
        daily_pnl = ctx.session.state.get(StateKeys.DAILY_PNL, 0)
        max_loss = ctx.session.state.get(StateKeys.APP_MAX_DAILY_LOSS, DEFAULT_MAX_DAILY_LOSS)

        should_stop = current_time >= square_off_time or daily_pnl <= -max_loss

        if should_stop:
            reason = "square_off_time" if current_time >= square_off_time else "max_loss_breached"
            ctx.session.state[StateKeys.STOP_REASON] = reason
            ctx.session.state[StateKeys.PHASE] = "eod"

        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_stop),
        )

        if not should_stop:
            interval = ctx.session.state.get(StateKeys.MONITORING_INTERVAL, DEFAULT_MONITORING_INTERVAL)
            await asyncio.sleep(interval)
