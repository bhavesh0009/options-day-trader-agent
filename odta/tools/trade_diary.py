from odta.db.connection import get_db_connection
from odta.utils.json_helpers import convert_rows_to_dicts


def read_trade_diary(last_n_trades: int = 15, include_daily_summaries: bool = True) -> dict:
    """Read recent trades and learnings from the trade diary.

    Use this at the start of each day to review past performance, identify
    recurring patterns, and avoid repeating mistakes.

    Args:
        last_n_trades: Number of recent trades to retrieve (default 15).
        include_daily_summaries: Whether to include daily summary entries.

    Returns:
        dict with recent trades, common patterns, and learnings
    """
    conn = get_db_connection()

    trades = conn.execute(
        """
        SELECT trade_date, symbol, option_symbol, direction, entry_price, exit_price,
               quantity, pnl, entry_rationale, exit_rationale, learnings, mistakes, tags
        FROM trade_diary
        WHERE symbol IS NOT NULL
        ORDER BY trade_date DESC, entry_time DESC
        LIMIT ?
    """,
        [last_n_trades],
    ).fetchall()

    columns = [
        "trade_date", "symbol", "option_symbol", "direction", "entry_price",
        "exit_price", "quantity", "pnl", "entry_rationale", "exit_rationale",
        "learnings", "mistakes", "tags",
    ]

    result = {
        "status": "success",
        "trades": convert_rows_to_dicts(trades, columns),
    }

    if include_daily_summaries:
        summaries = conn.execute("""
            SELECT DISTINCT trade_date, daily_summary, market_conditions
            FROM trade_diary
            WHERE daily_summary IS NOT NULL
            ORDER BY trade_date DESC
            LIMIT 5
        """).fetchall()
        summary_columns = ["date", "summary", "conditions"]
        result["daily_summaries"] = convert_rows_to_dicts(summaries, summary_columns)

    return result


def write_trade_diary(
    trade_date: str,
    symbol: str,
    option_symbol: str,
    direction: str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    pnl: float,
    entry_rationale: str,
    exit_rationale: str,
    market_conditions: str = "",
    learnings: str = "",
    mistakes: str = "",
    daily_summary: str = "",
    tags: str = "",
) -> dict:
    """Write a trade entry or daily summary to the trade diary.

    Call this after exiting a trade or at end of day for the daily summary.

    Args:
        trade_date: Date of the trade (YYYY-MM-DD).
        symbol: Stock symbol.
        option_symbol: Full option symbol (e.g., RELIANCE25JAN2500CE).
        direction: BUY_CE or BUY_PE.
        entry_price: Entry premium price.
        exit_price: Exit premium price.
        quantity: Number of shares/lots traded.
        pnl: Profit/loss in rupees.
        entry_rationale: Why the trade was entered.
        exit_rationale: Why the trade was exited.
        market_conditions: Overall market view during the trade.
        learnings: What was learned from this trade.
        mistakes: What went wrong (self-critique).
        daily_summary: End-of-day summary (one per day).
        tags: Comma-separated tags (e.g., "breakout,momentum").

    Returns:
        dict with status and entry id
    """
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO trade_diary
        (trade_date, symbol, option_symbol, direction, entry_price, exit_price,
         quantity, pnl, entry_rationale, exit_rationale, market_conditions,
         learnings, mistakes, daily_summary, tags, entry_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """,
        [
            trade_date, symbol, option_symbol, direction, entry_price, exit_price,
            quantity, pnl, entry_rationale, exit_rationale, market_conditions,
            learnings, mistakes, daily_summary, tags,
        ],
    )

    return {"status": "success", "message": f"Trade diary entry written for {symbol}"}
