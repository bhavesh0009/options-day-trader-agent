from datetime import datetime
import pytz
from google.adk.agents.callback_context import CallbackContext


def risk_manager_callback(
    callback_context: CallbackContext,
    tool_name: str,
    tool_args: dict,
) -> dict | None:
    """Intercepts order-related tool calls and enforces risk guardrails.

    Returns None to allow the tool call, or a dict to reject it.
    When a dict is returned, ADK skips the tool execution and returns
    the dict as the tool result -- the LLM sees the rejection reason.
    """
    ORDER_TOOLS = {"place_order", "modify_order"}

    if tool_name not in ORDER_TOOLS:
        return None  # non-order tools pass through

    state = callback_context.state

    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    # Rule 1: Daily loss limit
    daily_pnl = state.get("daily_pnl", 0)
    max_loss = state.get("app:max_daily_loss", 5000)
    if daily_pnl <= -max_loss:
        return {
            "status": "REJECTED",
            "reason": (
                f"Daily loss limit (Rs {max_loss}) breached. "
                f"Current P&L: Rs {daily_pnl}. No further trading allowed."
            ),
        }

    # Rule 2: Position count (only for new orders)
    if tool_name == "place_order":
        open_count = state.get("open_positions_count", 0)
        max_positions = state.get("app:max_open_positions", 2)
        if open_count >= max_positions:
            return {
                "status": "REJECTED",
                "reason": (
                    f"Max positions ({max_positions}) already open. "
                    "Close an existing position first."
                ),
            }

    # Rule 3: Time check (no new BUY entries near close)
    square_off_time = state.get("app:square_off_time", "15:00")
    if now.strftime("%H:%M") >= square_off_time:
        transaction_type = tool_args.get(
            "transactiontype", tool_args.get("transaction_type", "")
        )
        if transaction_type.upper() == "BUY":
            return {
                "status": "REJECTED",
                "reason": (
                    f"Past square-off time ({square_off_time}). "
                    "No new BUY orders allowed."
                ),
            }

    # Rule 4: Ban list check
    symbol = tool_args.get("tradingsymbol", tool_args.get("symbol", ""))
    if symbol and _is_banned(symbol):
        return {
            "status": "REJECTED",
            "reason": f"{symbol} is in the F&O ban list. Cannot trade banned securities.",
        }

    return None  # all checks passed


def _is_banned(symbol: str) -> bool:
    """Check if a stock is in the ban list."""
    from odta.db.connection import get_db_connection
    from datetime import date

    conn = get_db_connection()
    base_symbols = conn.execute(
        """
        SELECT symbol FROM ban_list WHERE ban_date = ?
    """,
        [date.today().isoformat()],
    ).fetchall()

    banned = {s[0].upper() for s in base_symbols}
    return any(symbol.upper().startswith(b) for b in banned)
