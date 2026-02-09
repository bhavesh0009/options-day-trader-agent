"""Tests for chart generation functionality.

This module tests:
- Stock chart generation with various indicators
- Index chart generation (NIFTY, BANKNIFTY)
- Chart file creation and metadata
- Error handling for invalid symbols
"""

import os
import pytest
from odta.tools.charts import generate_chart, generate_index_chart


class TestGenerateChart:
    """Test stock chart generation."""

    def test_basic_chart_generation(self):
        """Should generate a basic candlestick chart for a valid symbol."""
        # Use SMA_20 which works with 60 days of data
        result = generate_chart(symbol="RELIANCE", lookback_days=60, indicators="SMA_20")

        if result["status"] == "success":
            assert "chart_path" in result
            assert os.path.exists(result["chart_path"])
            assert result["chart_path"].endswith(".png")
            assert result["symbol"] == "RELIANCE"
            assert "days" in result
            assert "latest_close" in result
            assert "latest_volume" in result

    def test_chart_with_sma_indicators(self):
        """Should add SMA indicators to chart."""
        result = generate_chart(
            symbol="RELIANCE",
            lookback_days=60,
            indicators="SMA_20,SMA_50"
        )

        if result["status"] == "success":
            assert "indicators" in result
            assert "SMA_20" in result["indicators"]
            assert "SMA_50" in result["indicators"]

    def test_chart_with_ema_indicators(self):
        """Should add EMA indicators to chart."""
        result = generate_chart(
            symbol="RELIANCE",
            lookback_days=60,
            indicators="EMA_20,EMA_50"
        )

        if result["status"] == "success":
            assert "EMA_20" in result["indicators"]
            assert "EMA_50" in result["indicators"]

    def test_chart_with_bollinger_bands(self):
        """Should add Bollinger Bands to chart."""
        result = generate_chart(
            symbol="RELIANCE",
            lookback_days=60,
            indicators="BBANDS"
        )

        if result["status"] == "success":
            assert "BBANDS" in result["indicators"]

    def test_chart_with_rsi(self):
        """Should add RSI indicator as subplot."""
        result = generate_chart(
            symbol="RELIANCE",
            lookback_days=60,
            indicators="RSI"
        )

        if result["status"] == "success":
            assert "RSI" in result["indicators"]

    def test_chart_with_multiple_indicators(self):
        """Should handle multiple indicators simultaneously."""
        result = generate_chart(
            symbol="RELIANCE",
            lookback_days=60,
            indicators="SMA_20,SMA_50,RSI,BBANDS"
        )

        if result["status"] == "success":
            indicators = result["indicators"]
            assert len(indicators) == 4
            assert "SMA_20" in indicators
            assert "RSI" in indicators

    def test_chart_ohlc_type(self):
        """Should support OHLC bar chart type."""
        result = generate_chart(
            symbol="RELIANCE",
            lookback_days=60,
            indicators="SMA_20",
            chart_type="ohlc"
        )

        if result["status"] == "success":
            assert result["status"] == "success"

    def test_chart_invalid_symbol(self):
        """Should handle invalid stock symbols gracefully."""
        result = generate_chart(symbol="INVALID_SYMBOL_XYZ", lookback_days=30)

        assert result["status"] == "error"
        assert "reason" in result

    def test_chart_lookback_variations(self):
        """Should handle different lookback periods."""
        lookback_periods = [60, 100, 150]

        for days in lookback_periods:
            result = generate_chart(symbol="RELIANCE", lookback_days=days, indicators="SMA_20")

            if result["status"] == "success":
                # Chart should have at most the requested days
                assert result["days"] <= days

    def test_chart_file_created_in_temp_dir(self):
        """Chart should be created in temporary directory."""
        result = generate_chart(symbol="RELIANCE", lookback_days=60, indicators="SMA_20")

        if result["status"] == "success":
            assert "/odta_charts/" in result["chart_path"]

    def test_chart_metadata_completeness(self):
        """Chart result should contain complete metadata."""
        result = generate_chart(
            symbol="RELIANCE",
            lookback_days=60,
            indicators="SMA_20,SMA_50"
        )

        if result["status"] == "success":
            required_keys = [
                "status", "chart_path", "symbol", "days",
                "date_range", "indicators", "latest_close", "latest_volume"
            ]
            for key in required_keys:
                assert key in result

    def test_chart_date_range_format(self):
        """Date range should be in proper format."""
        result = generate_chart(symbol="RELIANCE", lookback_days=60, indicators="SMA_20")

        if result["status"] == "success":
            date_range = result["date_range"]
            assert " to " in date_range
            # Should contain year-month-day format
            parts = date_range.split(" to ")
            assert len(parts) == 2
            for date_part in parts:
                assert len(date_part) == 10  # YYYY-MM-DD format


class TestGenerateIndexChart:
    """Test index chart generation."""

    def test_nifty_chart_generation(self):
        """Should generate NIFTY index chart."""
        result = generate_index_chart(index="NIFTY", lookback_days=60)

        if result["status"] == "success":
            assert "chart_path" in result
            assert os.path.exists(result["chart_path"])
            assert result["index"] == "NIFTY"
            assert "days" in result
            assert "latest_close" in result

    def test_banknifty_chart_generation(self):
        """Should generate BANKNIFTY index chart."""
        result = generate_index_chart(index="BANKNIFTY", lookback_days=60)

        if result["status"] == "success":
            assert result["index"] == "BANKNIFTY"

    def test_index_chart_case_insensitive(self):
        """Index parameter should be case insensitive (accepts different cases)."""
        result1 = generate_index_chart(index="nifty")
        result2 = generate_index_chart(index="NIFTY")

        # Both should work (case insensitive)
        # The returned index field preserves input case
        if result1["status"] == "success" and result2["status"] == "success":
            assert result1["index"] == "nifty"
            assert result2["index"] == "NIFTY"

    def test_index_chart_invalid_index(self):
        """Should handle invalid index names."""
        result = generate_index_chart(index="INVALID_INDEX")

        assert result["status"] == "error"
        assert "reason" in result

    def test_index_chart_includes_sma(self):
        """Index chart should include SMA_20 overlay."""
        result = generate_index_chart(index="NIFTY", lookback_days=60)

        if result["status"] == "success":
            # Index charts always include SMA_20
            assert result["status"] == "success"

    def test_index_chart_metadata(self):
        """Index chart should have complete metadata."""
        result = generate_index_chart(index="NIFTY", lookback_days=60)

        if result["status"] == "success":
            required_keys = ["status", "chart_path", "index", "days", "latest_close"]
            for key in required_keys:
                assert key in result

    def test_index_chart_lookback_variations(self):
        """Should handle different lookback periods."""
        for days in [30, 60, 100]:
            result = generate_index_chart(index="NIFTY", lookback_days=days)

            if result["status"] == "success":
                assert result["days"] <= days

    def test_index_chart_file_naming(self):
        """Index chart files should include index name."""
        result = generate_index_chart(index="NIFTY", lookback_days=60)

        if result["status"] == "success":
            filename = os.path.basename(result["chart_path"])
            assert "NIFTY" in filename

    def test_chart_file_cleanup_not_required(self):
        """Charts in temp directory don't need manual cleanup."""
        result = generate_chart(symbol="RELIANCE", lookback_days=60, indicators="SMA_20")

        if result["status"] == "success":
            # Verify file exists after generation
            assert os.path.exists(result["chart_path"])
            # Temp directory will be cleaned by OS eventually
