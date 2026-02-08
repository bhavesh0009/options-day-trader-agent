from odta.db.connection import get_db_connection


def query_database(sql: str, explanation: str) -> dict:
    """Execute a read-only SQL query against the trading database.

    Use this to query historical OHLCV data, F&O securities list, ban list,
    and trade diary. Always provide an explanation of why you need this data.

    Available tables:
    - daily_ohlcv: symbol, date, series, open, high, low, close, prev_close, volume, value, vwap, trades, delivery_volume, delivery_pct
    - fno_stocks: symbol, company_name, lot_size, sector, industry, last_updated
    - index_ohlcv: index_name, date, open, high, close, low (Nifty 50, BankNifty)
    - ban_list: symbol, ban_date
    - trade_diary: id, trade_date, symbol, option_symbol, entry/exit details, rationale, learnings
    - decision_log: id, timestamp, trade_date, phase, action_type, symbol, summary, reasoning

    Args:
        sql: SQL query to execute. Must be a SELECT statement.
        explanation: Why this query is needed for the current trading decision.

    Returns:
        dict with columns, rows, row_count, and status
    """
    sql_stripped = sql.strip()
    if not sql_stripped.upper().startswith("SELECT"):
        return {"status": "error", "reason": "Only SELECT queries are allowed."}

    try:
        conn = get_db_connection()
        result = conn.execute(sql_stripped).fetchall()
        columns = [desc[0] for desc in conn.description]
        return {
            "status": "success",
            "columns": columns,
            "rows": [list(row) for row in result],
            "row_count": len(result),
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
