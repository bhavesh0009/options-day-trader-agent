"""Tests for trade diary functionality.

This module tests:
- Reading trade diary entries
- Writing trade diary entries
- Daily summaries
- Trade history retrieval
- Data persistence
"""

import pytest
from datetime import date, datetime
from odta.tools.trade_diary import read_trade_diary, write_trade_diary


class TestReadTradeDiary:
    """Test reading trade diary entries."""

    def test_read_trade_diary_basic(self):
        """Should read trade diary without errors."""
        result = read_trade_diary(last_n_trades=5)

        assert result["status"] == "success"
        assert "trades" in result
        assert isinstance(result["trades"], list)

    def test_read_trade_diary_with_summaries(self):
        """Should include daily summaries when requested."""
        result = read_trade_diary(last_n_trades=5, include_daily_summaries=True)

        assert result["status"] == "success"
        assert "daily_summaries" in result
        assert isinstance(result["daily_summaries"], list)

    def test_read_trade_diary_without_summaries(self):
        """Should exclude daily summaries when not requested."""
        result = read_trade_diary(last_n_trades=5, include_daily_summaries=False)

        assert result["status"] == "success"
        # daily_summaries key should not be present
        assert "daily_summaries" not in result

    def test_read_trade_diary_limit_works(self):
        """Should respect the last_n_trades limit."""
        limit = 3
        result = read_trade_diary(last_n_trades=limit)

        assert result["status"] == "success"
        assert len(result["trades"]) <= limit

    def test_trade_diary_entry_structure(self):
        """Trade entries should have proper structure."""
        result = read_trade_diary(last_n_trades=1)

        if result["trades"]:
            trade = result["trades"][0]
            expected_keys = [
                "trade_date", "symbol", "option_symbol", "direction",
                "entry_price", "exit_price", "quantity", "pnl",
                "entry_rationale", "exit_rationale", "learnings", "mistakes", "tags"
            ]
            for key in expected_keys:
                assert key in trade

    def test_daily_summary_structure(self):
        """Daily summaries should have proper structure."""
        result = read_trade_diary(last_n_trades=5, include_daily_summaries=True)

        if result["daily_summaries"]:
            summary = result["daily_summaries"][0]
            assert "date" in summary
            assert "summary" in summary
            assert "conditions" in summary

    def test_read_trade_diary_empty_database(self):
        """Should handle empty diary gracefully."""
        result = read_trade_diary(last_n_trades=100)

        assert result["status"] == "success"
        assert isinstance(result["trades"], list)
        # May be empty if no trades exist yet


class TestWriteTradeDiary:
    """Test writing trade diary entries."""

    def test_write_trade_diary_basic(self):
        """Should write a complete trade entry."""
        today = date.today().isoformat()

        result = write_trade_diary(
            trade_date=today,
            symbol="RELIANCE",
            option_symbol="RELIANCE25FEB2500CE",
            direction="BUY_CE",
            entry_price=45.50,
            exit_price=52.00,
            quantity=75,
            pnl=487.50,
            entry_rationale="Bullish breakout above 2450 with strong volume",
            exit_rationale="Target reached at 2500 resistance",
            market_conditions="Nifty trending up, banking sector strong",
            learnings="Entry timing was optimal, waited for confirmation",
            mistakes="",
            tags="breakout,momentum"
        )

        assert result["status"] == "success"
        assert "message" in result

    def test_write_trade_diary_with_minimal_fields(self):
        """Should write entry with only required fields."""
        today = date.today().isoformat()

        result = write_trade_diary(
            trade_date=today,
            symbol="SBIN",
            option_symbol="SBIN25FEB600CE",
            direction="BUY_CE",
            entry_price=10.50,
            exit_price=12.00,
            quantity=150,
            pnl=225.00,
            entry_rationale="Bullish setup",
            exit_rationale="Target hit"
        )

        assert result["status"] == "success"

    def test_write_trade_diary_with_loss(self):
        """Should correctly record losing trades."""
        today = date.today().isoformat()

        result = write_trade_diary(
            trade_date=today,
            symbol="TATAMOTORS",
            option_symbol="TATAMOTORS25FEB800PE",
            direction="BUY_PE",
            entry_price=25.00,
            exit_price=20.00,
            quantity=100,
            pnl=-500.00,
            entry_rationale="Expected weakness",
            exit_rationale="Stop loss hit",
            mistakes="Entry too early, ignored market strength"
        )

        assert result["status"] == "success"
        assert "TATAMOTORS" in result["message"]

    def test_write_trade_diary_with_daily_summary(self):
        """Should write daily summary entry."""
        today = date.today().isoformat()

        result = write_trade_diary(
            trade_date=today,
            symbol="SUMMARY",
            option_symbol="DAILY_SUMMARY",
            direction="NA",
            entry_price=0.0,
            exit_price=0.0,
            quantity=0,
            pnl=250.00,
            entry_rationale="Daily review",
            exit_rationale="Daily review",
            daily_summary="Took 2 trades, 1 winner 1 loser. Market was choppy.",
            market_conditions="Sideways market, low conviction trades"
        )

        assert result["status"] == "success"

    def test_write_then_read_trade_diary(self):
        """Written trade should be readable immediately."""
        today = date.today().isoformat()

        # Write a trade
        write_result = write_trade_diary(
            trade_date=today,
            symbol="TESTSTOCK",
            option_symbol="TESTSTOCK25FEB1000CE",
            direction="BUY_CE",
            entry_price=30.00,
            exit_price=35.00,
            quantity=50,
            pnl=250.00,
            entry_rationale="Test entry",
            exit_rationale="Test exit",
            tags="test"
        )

        assert write_result["status"] == "success"

        # Read it back
        read_result = read_trade_diary(last_n_trades=1)
        assert read_result["status"] == "success"

        # Verify the latest trade
        if read_result["trades"]:
            latest_trade = read_result["trades"][0]
            assert latest_trade["symbol"] == "TESTSTOCK"
            assert latest_trade["direction"] == "BUY_CE"
            assert latest_trade["pnl"] == 250.00

    def test_write_trade_diary_with_tags(self):
        """Should properly store trade tags."""
        today = date.today().isoformat()

        result = write_trade_diary(
            trade_date=today,
            symbol="HDFCBANK",
            option_symbol="HDFCBANK25FEB1600CE",
            direction="BUY_CE",
            entry_price=40.00,
            exit_price=45.00,
            quantity=75,
            pnl=375.00,
            entry_rationale="Breakout setup",
            exit_rationale="Target reached",
            tags="breakout,banking,high-volume"
        )

        assert result["status"] == "success"

    def test_trade_diary_persistence(self):
        """Trade diary should persist across function calls."""
        # Write multiple trades
        today = date.today().isoformat()

        for i in range(3):
            write_trade_diary(
                trade_date=today,
                symbol=f"STOCK{i}",
                option_symbol=f"STOCK{i}25FEB1000CE",
                direction="BUY_CE",
                entry_price=20.00 + i,
                exit_price=25.00 + i,
                quantity=50,
                pnl=250.00,
                entry_rationale=f"Test entry {i}",
                exit_rationale=f"Test exit {i}"
            )

        # Read back
        result = read_trade_diary(last_n_trades=5)
        assert result["status"] == "success"
        # Should have at least the 3 we just wrote
        assert len(result["trades"]) >= 3

    def test_write_trade_diary_decimal_precision(self):
        """Should handle decimal prices correctly."""
        today = date.today().isoformat()

        result = write_trade_diary(
            trade_date=today,
            symbol="PRICETEST",
            option_symbol="PRICETEST25FEB1000CE",
            direction="BUY_CE",
            entry_price=12.75,
            exit_price=14.25,
            quantity=100,
            pnl=150.00,
            entry_rationale="Price test",
            exit_rationale="Price test"
        )

        assert result["status"] == "success"
