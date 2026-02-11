from unittest.mock import MagicMock, patch

from odta.risk.callbacks import risk_manager_callback
from odta.constants import (
    StateKeys,
    DEFAULT_MAX_DAILY_LOSS,
    DEFAULT_MAX_OPEN_POSITIONS,
    SQUARE_OFF_TIME_STR,
)


def _make_tool_context(state: dict) -> MagicMock:
    """Create mock tool_context with state."""
    ctx = MagicMock()
    ctx.state = state
    return ctx


def _make_tool(name: str) -> MagicMock:
    """Create mock tool with name."""
    tool = MagicMock()
    tool.name = name
    return tool


def test_allow_non_order_tools():
    """Risk callback should pass through non-order tools."""
    tool = _make_tool("get_ltp_data")
    ctx = _make_tool_context({})
    result = risk_manager_callback(tool, {}, ctx)
    assert result is None


def test_allow_valid_order():
    """Risk callback should return None for valid orders."""
    tool = _make_tool("place_order")
    ctx = _make_tool_context({
        StateKeys.DAILY_PNL: 0,
        StateKeys.OPEN_POSITIONS_COUNT: 0,
        StateKeys.APP_MAX_DAILY_LOSS: DEFAULT_MAX_DAILY_LOSS,
        StateKeys.APP_MAX_OPEN_POSITIONS: DEFAULT_MAX_OPEN_POSITIONS,
        StateKeys.APP_SQUARE_OFF_TIME: SQUARE_OFF_TIME_STR,
    })
    with patch("odta.risk.callbacks._is_banned", return_value=False):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "10:00"
            result = risk_manager_callback(tool, {"symbol": "RELIANCE"}, ctx)
    assert result is None


def test_reject_when_daily_loss_exceeded():
    """Risk callback should reject orders when daily loss limit is hit."""
    tool = _make_tool("place_order")
    ctx = _make_tool_context({
        StateKeys.DAILY_PNL: -DEFAULT_MAX_DAILY_LOSS,
        StateKeys.APP_MAX_DAILY_LOSS: DEFAULT_MAX_DAILY_LOSS,
    })
    result = risk_manager_callback(tool, {}, ctx)
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "loss limit" in result["reason"].lower()


def test_reject_when_max_positions_reached():
    """Risk callback should reject new orders when position limit reached."""
    tool = _make_tool("place_order")
    ctx = _make_tool_context({
        StateKeys.DAILY_PNL: 0,
        StateKeys.OPEN_POSITIONS_COUNT: DEFAULT_MAX_OPEN_POSITIONS,
        StateKeys.APP_MAX_DAILY_LOSS: DEFAULT_MAX_DAILY_LOSS,
        StateKeys.APP_MAX_OPEN_POSITIONS: DEFAULT_MAX_OPEN_POSITIONS,
    })
    result = risk_manager_callback(tool, {}, ctx)
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "positions" in result["reason"].lower()


def test_reject_after_square_off_time():
    """Risk callback should reject BUY orders after square-off time."""
    tool = _make_tool("place_order")
    ctx = _make_tool_context({
        StateKeys.DAILY_PNL: 0,
        StateKeys.OPEN_POSITIONS_COUNT: 0,
        StateKeys.APP_MAX_DAILY_LOSS: DEFAULT_MAX_DAILY_LOSS,
        StateKeys.APP_MAX_OPEN_POSITIONS: DEFAULT_MAX_OPEN_POSITIONS,
        StateKeys.APP_SQUARE_OFF_TIME: SQUARE_OFF_TIME_STR,
    })
    with patch("odta.risk.callbacks._is_banned", return_value=False):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "15:05"
            result = risk_manager_callback(
                tool,
                {"transaction_type": "BUY", "symbol": "RELIANCE"},
                ctx,
            )
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "square-off" in result["reason"].lower()


def test_reject_banned_securities():
    """Risk callback should reject orders for banned stocks."""
    tool = _make_tool("place_order")
    ctx = _make_tool_context({
        StateKeys.DAILY_PNL: 0,
        StateKeys.OPEN_POSITIONS_COUNT: 0,
        StateKeys.APP_MAX_DAILY_LOSS: DEFAULT_MAX_DAILY_LOSS,
        StateKeys.APP_MAX_OPEN_POSITIONS: DEFAULT_MAX_OPEN_POSITIONS,
        StateKeys.APP_SQUARE_OFF_TIME: SQUARE_OFF_TIME_STR,
    })
    with patch("odta.risk.callbacks._is_banned", return_value=True):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "10:00"
            result = risk_manager_callback(
                tool, {"symbol": "BANNED_STOCK27FEB1500CE"}, ctx,
            )
    assert result is not None
    assert result["status"] == "REJECTED"
    assert "ban" in result["reason"].lower()


def test_reject_equity_orders():
    """Risk callback should reject equity orders - only allow options."""
    tool = _make_tool("place_order")
    ctx = _make_tool_context({
        StateKeys.DAILY_PNL: 0,
        StateKeys.OPEN_POSITIONS_COUNT: 0,
        StateKeys.APP_MAX_DAILY_LOSS: DEFAULT_MAX_DAILY_LOSS,
        StateKeys.APP_MAX_OPEN_POSITIONS: DEFAULT_MAX_OPEN_POSITIONS,
        StateKeys.APP_SQUARE_OFF_TIME: SQUARE_OFF_TIME_STR,
    })

    # Test various equity suffixes
    equity_symbols = [
        "RELIANCE-EQ",
        "INFY-BE",
        "TCS-BL",
        "KOTAKBANK-AF",
        "ITC-IQ",
        "SBIN-RL",
    ]

    with patch("odta.risk.callbacks._is_banned", return_value=False):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "10:00"
            for symbol in equity_symbols:
                result = risk_manager_callback(
                    tool, {"tradingsymbol": symbol}, ctx,
                )
                assert result is not None, f"Should reject equity order: {symbol}"
                assert result["status"] == "REJECTED"
                assert "EQUITY ORDER REJECTED" in result["reason"]


def test_allow_option_orders():
    """Risk callback should allow valid option orders (CE/PE)."""
    tool = _make_tool("place_order")
    ctx = _make_tool_context({
        StateKeys.DAILY_PNL: 0,
        StateKeys.OPEN_POSITIONS_COUNT: 0,
        StateKeys.APP_MAX_DAILY_LOSS: DEFAULT_MAX_DAILY_LOSS,
        StateKeys.APP_MAX_OPEN_POSITIONS: DEFAULT_MAX_OPEN_POSITIONS,
        StateKeys.APP_SQUARE_OFF_TIME: SQUARE_OFF_TIME_STR,
    })

    # Test valid option contracts
    option_symbols = [
        "RELIANCE27FEB3000CE",
        "INFY28FEB1600PE",
        "TCS27MAR4500CE",
        "KOTAKBANK27FEB1800PE",
    ]

    with patch("odta.risk.callbacks._is_banned", return_value=False):
        with patch("odta.risk.callbacks.datetime") as mock_dt:
            mock_dt.now.return_value.strftime.return_value = "10:00"
            for symbol in option_symbols:
                result = risk_manager_callback(
                    tool, {"tradingsymbol": symbol, "transaction_type": "BUY"}, ctx,
                )
                assert result is None, f"Should allow option order: {symbol}"
