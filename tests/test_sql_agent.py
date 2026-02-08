from odta.tools.sql_agent import query_database


def test_reject_non_select_query():
    """SQL agent should reject INSERT/UPDATE/DELETE queries."""
    result = query_database("INSERT INTO daily_ohlcv VALUES (1)", "test")
    assert result["status"] == "error"
    assert "SELECT" in result["reason"]


def test_reject_delete_query():
    """SQL agent should reject DELETE queries."""
    result = query_database("DELETE FROM daily_ohlcv", "test")
    assert result["status"] == "error"


def test_reject_update_query():
    """SQL agent should reject UPDATE queries."""
    result = query_database("UPDATE daily_ohlcv SET close = 100", "test")
    assert result["status"] == "error"


def test_select_query_succeeds():
    """SQL agent should execute valid SELECT queries."""
    result = query_database(
        "SELECT COUNT(*) as cnt FROM daily_ohlcv",
        "checking row count",
    )
    assert result["status"] == "success"
    assert result["row_count"] == 1
    assert result["rows"][0][0] > 0
