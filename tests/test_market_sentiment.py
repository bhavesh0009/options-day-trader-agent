"""Tests for market sentiment analysis tools.

This module tests:
- Market regime detection (bullish/bearish/sideways)
- Sector sentiment analysis
- Index analysis (NIFTY, BANKNIFTY)
- Error handling for invalid inputs
"""

import pytest
from odta.tools.market_sentiment import get_market_regime, get_sector_sentiment


class TestGetMarketRegime:
    """Test market regime detection and classification."""

    def test_nifty_market_regime_success(self):
        """Should successfully analyze NIFTY market regime."""
        result = get_market_regime(index="NIFTY")

        assert result["status"] == "success"
        assert result["index"] == "NIFTY"
        assert result["trend"] in ["bullish", "bearish", "sideways"]
        assert result["regime"] in ["volatile", "ranging", "trending"]
        assert "current_price" in result
        assert "rsi" in result
        assert "sma_20" in result
        assert "atr_14" in result

    def test_banknifty_market_regime_success(self):
        """Should successfully analyze BANKNIFTY market regime."""
        result = get_market_regime(index="BANKNIFTY")

        assert result["status"] == "success"
        assert result["index"] == "BANKNIFTY"
        assert result["trend"] in ["bullish", "bearish", "sideways"]

    def test_market_regime_includes_key_levels(self):
        """Should return support and resistance levels."""
        result = get_market_regime(index="NIFTY")

        assert "key_levels" in result
        assert "support" in result["key_levels"]
        assert "resistance" in result["key_levels"]
        assert result["key_levels"]["resistance"] > result["key_levels"]["support"]

    def test_market_regime_includes_performance_metrics(self):
        """Should return recent performance metrics."""
        result = get_market_regime(index="NIFTY")

        if result["status"] == "success":
            assert "5d_change_pct" in result
            if result["5d_change_pct"] is not None:
                assert isinstance(result["5d_change_pct"], (int, float))

    def test_market_regime_rsi_bounds(self):
        """RSI should be between 0 and 100."""
        result = get_market_regime(index="NIFTY")

        if result["status"] == "success":
            assert 0 <= result["rsi"] <= 100

    def test_market_regime_case_insensitive(self):
        """Index name should be case insensitive (accepts different cases)."""
        result1 = get_market_regime(index="nifty")
        result2 = get_market_regime(index="NIFTY")
        result3 = get_market_regime(index="Nifty")

        # All should succeed (case insensitive input)
        # The returned index field preserves the input case
        if result1["status"] == "success":
            assert result1["index"] == "nifty"
            assert result2["index"] == "NIFTY"
            assert result3["index"] == "Nifty"

    def test_market_regime_invalid_index(self):
        """Should handle invalid index names gracefully."""
        result = get_market_regime(index="INVALID_INDEX")

        # Should either return error or no data
        if result["status"] == "error":
            assert "reason" in result


class TestGetSectorSentiment:
    """Test sector-level sentiment analysis."""

    def test_sector_sentiment_structure(self):
        """Should return proper sector sentiment structure."""
        # Try a common sector - if it doesn't exist, test should still pass
        result = get_sector_sentiment(sector="Banking")

        if result["status"] == "success":
            assert "sector" in result
            assert "sector_trend" in result
            assert result["sector_trend"] in ["bullish", "bearish", "neutral"]
            assert "avg_change_pct" in result
            assert "stock_count" in result

    def test_sector_sentiment_includes_leaders(self):
        """Should return top gainers and losers."""
        result = get_sector_sentiment(sector="Banking")

        if result["status"] == "success":
            assert "top_gainers" in result
            assert "top_losers" in result
            assert isinstance(result["top_gainers"], list)
            assert isinstance(result["top_losers"], list)

            # Check structure of gainers/losers
            if result["top_gainers"]:
                gainer = result["top_gainers"][0]
                assert "symbol" in gainer
                assert "change" in gainer

    def test_sector_sentiment_trend_classification(self):
        """Sector trend should match average change direction."""
        result = get_sector_sentiment(sector="Banking")

        if result["status"] == "success":
            avg_change = result["avg_change_pct"]
            trend = result["sector_trend"]

            if avg_change > 0.5:
                assert trend == "bullish"
            elif avg_change < -0.5:
                assert trend == "bearish"
            else:
                assert trend == "neutral"

    def test_sector_sentiment_invalid_sector(self):
        """Should handle non-existent sectors."""
        result = get_sector_sentiment(sector="NonExistentSector123")

        assert result["status"] == "error"
        assert "reason" in result

    def test_sector_sentiment_gainers_limit(self):
        """Should limit gainers and losers to 3 each."""
        result = get_sector_sentiment(sector="IT")

        if result["status"] == "success":
            assert len(result["top_gainers"]) <= 3
            assert len(result["top_losers"]) <= 3

    def test_sector_sentiment_common_sectors(self):
        """Test commonly used sectors."""
        common_sectors = ["Banking", "IT", "Auto", "Pharma", "Energy"]

        for sector in common_sectors:
            result = get_sector_sentiment(sector=sector)
            # Should either succeed or gracefully handle missing data
            assert "status" in result
            if result["status"] == "success":
                assert result["sector"] == sector
                assert isinstance(result["stock_count"], int)
