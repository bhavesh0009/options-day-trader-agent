import asyncio
from datetime import datetime
from typing import AsyncGenerator

import pytz
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions


class LoopController(BaseAgent):
    """Non-LLM agent that checks market hours and P&L limits.

    Runs after each trader_agent iteration. Sleeps for the adaptive
    monitoring interval, then checks if the trading loop should end.
    """

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)
        current_time = now.strftime("%H:%M")

        square_off_time = ctx.session.state.get("app:square_off_time", "15:00")
        daily_pnl = ctx.session.state.get("daily_pnl", 0)
        max_loss = ctx.session.state.get("app:max_daily_loss", 5000)

        should_stop = current_time >= square_off_time or daily_pnl <= -max_loss

        if should_stop:
            reason = "square_off_time" if current_time >= square_off_time else "max_loss_breached"
            ctx.session.state["stop_reason"] = reason
            ctx.session.state["phase"] = "eod"

        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_stop),
        )

        if not should_stop:
            interval = ctx.session.state.get("monitoring_interval", 120)
            await asyncio.sleep(interval)
