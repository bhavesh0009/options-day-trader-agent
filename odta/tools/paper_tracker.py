from odta.db.connection import get_db_connection


def get_paper_positions() -> dict:
    """Get current paper trading positions and P&L.

    Use this instead of get_positions when in paper trading mode.
    Returns simulated positions tracked locally.

    Returns:
        dict with open positions, closed positions today, and total P&L
    """
    conn = get_db_connection()
    from datetime import date

    open_positions = conn.execute(
        """
        SELECT symbol, option_symbol, transaction_type, quantity, entry_price, entry_time
        FROM paper_positions
        WHERE trade_date = ? AND status = 'OPEN'
    """,
        [date.today().isoformat()],
    ).fetchall()

    closed_today = conn.execute(
        """
        SELECT symbol, option_symbol, entry_price, exit_price, quantity, pnl
        FROM paper_positions
        WHERE trade_date = ? AND status = 'CLOSED'
    """,
        [date.today().isoformat()],
    ).fetchall()

    total_pnl = sum(c[5] for c in closed_today if c[5]) if closed_today else 0

    return {
        "status": "success",
        "open_positions": [
            {
                "symbol": p[0], "option_symbol": p[1], "type": p[2],
                "qty": p[3], "entry_price": float(p[4]), "entry_time": str(p[5]),
            }
            for p in open_positions
        ],
        "closed_today": [
            {
                "symbol": c[0], "option_symbol": c[1], "entry": float(c[2]),
                "exit": float(c[3]), "qty": c[4], "pnl": float(c[5]),
            }
            for c in closed_today
        ],
        "open_count": len(open_positions),
        "realized_pnl": float(total_pnl),
    }


def record_paper_trade(
    symbol: str,
    option_symbol: str,
    transaction_type: str,
    quantity: int,
    price: float,
    action: str,
) -> dict:
    """Record a paper trade entry or exit.

    Called by the after_tool_callback when place_order succeeds in paper mode.

    Args:
        symbol: Stock symbol.
        option_symbol: Full option symbol.
        transaction_type: BUY or SELL.
        quantity: Number of shares.
        price: Execution price.
        action: "ENTRY" or "EXIT"

    Returns:
        dict with status
    """
    from datetime import date, datetime

    conn = get_db_connection()

    if action == "ENTRY":
        conn.execute(
            """
            INSERT INTO paper_positions
            (trade_date, symbol, option_symbol, transaction_type, quantity, entry_price, entry_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')
        """,
            [
                date.today().isoformat(), symbol, option_symbol,
                transaction_type, quantity, price, datetime.now().isoformat(),
            ],
        )
    elif action == "EXIT":
        position = conn.execute(
            """
            SELECT id, entry_price, quantity FROM paper_positions
            WHERE option_symbol = ? AND status = 'OPEN'
            ORDER BY entry_time DESC LIMIT 1
        """,
            [option_symbol],
        ).fetchone()

        if position:
            pnl = (price - position[1]) * position[2]
            conn.execute(
                """
                UPDATE paper_positions SET exit_price = ?, exit_time = ?, status = 'CLOSED', pnl = ?
                WHERE id = ?
            """,
                [price, datetime.now().isoformat(), pnl, position[0]],
            )

    return {"status": "success", "action": action}
