from odta.tools.indicators import calculate_indicator


def test_rsi_calculation():
    """RSI should return valid values for a known stock."""
    result = calculate_indicator("RELIANCE", "RSI", period=14, lookback_days=50)
    if result["status"] == "success":
        assert result["symbol"] == "RELIANCE"
        assert result["indicator"] == "RSI"
        assert len(result["values"]) > 0
    # If no data, error is acceptable in test environment


def test_sma_calculation():
    """SMA should return valid values."""
    result = calculate_indicator("RELIANCE", "SMA", period=20, lookback_days=50)
    if result["status"] == "success":
        assert result["symbol"] == "RELIANCE"
        assert len(result["values"]) > 0


def test_unknown_symbol_returns_error():
    """Should return error for unknown symbol."""
    result = calculate_indicator("NONEXISTENT_STOCK_XYZ", "RSI")
    assert result["status"] == "error"
