from unittest.mock import MagicMock, patch
from odta.risk.callbacks import risk_manager_callback


def _make_callback_context(state: dict) -> MagicMock:
    ctx = MagicMock()
    ctx.state = state
    return ctx


def test_allow_non_order_tools():
    """Risk callback should pass through non-order tools."""
    ctx = _make_callback_context({})
    result = risk_manager_callback(ctx, "get_ltp_data", {})
    assert result is None


def test_allow_valid_order():
    """Risk callback should return None for valid orders."""
    ctx = _make_callback_context({
        "daily_pnl": 0,
        "open_positions_count": 0,
        "app:max_daily_loss": 5000,
        "app:max_open_positions": 2,
        "app:square_off_time": "15:00",
    })
    with patch("odta.risk.callbacks._is_banned", return_value=False):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "10:00"
            result = risk_manager_callback(ctx, "place_order", {"symbol": "RELIANCE"})
    assert result is None


def test_reject_when_daily_loss_exceeded():
    """Risk callback should reject orders when daily loss limit is hit."""
    ctx = _make_callback_context({
        "daily_pnl": -5000,
        "app:max_daily_loss": 5000,
    })
    result = risk_manager_callback(ctx, "place_order", {})
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "loss limit" in result["reason"].lower()


def test_reject_when_max_positions_reached():
    """Risk callback should reject new orders when position limit reached."""
    ctx = _make_callback_context({
        "daily_pnl": 0,
        "open_positions_count": 2,
        "app:max_daily_loss": 5000,
        "app:max_open_positions": 2,
    })
    result = risk_manager_callback(ctx, "place_order", {})
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "positions" in result["reason"].lower()


def test_reject_after_square_off_time():
    """Risk callback should reject BUY orders after square-off time."""
    ctx = _make_callback_context({
        "daily_pnl": 0,
        "open_positions_count": 0,
        "app:max_daily_loss": 5000,
        "app:max_open_positions": 2,
        "app:square_off_time": "15:00",
    })
    with patch("odta.risk.callbacks._is_banned", return_value=False):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "15:05"
            result = risk_manager_callback(
                ctx, "place_order",
                {"transaction_type": "BUY", "symbol": "RELIANCE"},
            )
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "square-off" in result["reason"].lower()


def test_reject_banned_securities():
    """Risk callback should reject orders for banned stocks."""
    ctx = _make_callback_context({
        "daily_pnl": 0,
        "open_positions_count": 0,
        "app:max_daily_loss": 5000,
        "app:max_open_positions": 2,
        "app:square_off_time": "15:00",
    })
    with patch("odta.risk.callbacks._is_banned", return_value=True):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "10:00"
            result = risk_manager_callback(
                ctx, "place_order", {"symbol": "BANNED_STOCK"},
            )
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "ban" in result["reason"].lower()
