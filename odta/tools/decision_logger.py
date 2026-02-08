from odta.db.connection import get_db_connection


def log_decision(
    phase: str,
    action_type: str,
    summary: str,
    reasoning: str,
    symbol: str = "",
    data_points: str = "{}",
    outcome: str = "",
) -> dict:
    """Log a trading decision for the workflow visualizer dashboard.

    Call this after EVERY significant decision: market analysis, stock screening,
    trade entry/exit, monitoring updates, or skip decisions.

    Args:
        phase: Current phase - pre_market / planning / execution / monitoring / eod
        action_type: Type - analysis / stock_selection / trade_entry / trade_exit / monitoring / skip
        summary: One-line summary of the decision.
        reasoning: Detailed reasoning and thought process behind the decision.
        symbol: Stock symbol (leave empty for market-level decisions).
        data_points: JSON string of indicators, prices, and levels used in the decision.
        outcome: Result of the action, if applicable.

    Returns:
        dict with status confirmation
    """
    from datetime import date

    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO decision_log (trade_date, phase, action_type, symbol, summary, reasoning, data_points, outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            date.today().isoformat(), phase, action_type,
            symbol or None, summary, reasoning, data_points, outcome,
        ],
    )

    return {"status": "success", "message": f"Decision logged: {summary}"}
