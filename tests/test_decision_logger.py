"""Tests for decision logging functionality.

This module tests:
- Logging trading decisions
- Decision phases (pre_market, execution, monitoring, eod)
- Action types (analysis, trade_entry, trade_exit, etc.)
- Data point tracking
- Decision retrieval
"""

import pytest
from datetime import date
from odta.tools.decision_logger import log_decision
from odta.db.connection import get_db_connection


class TestLogDecision:
    """Test decision logging functionality."""

    def test_log_decision_basic(self):
        """Should log a basic decision without errors."""
        result = log_decision(
            phase="pre_market",
            action_type="analysis",
            summary="Nifty showing bullish bias",
            reasoning="20-day SMA acting as support, RSI at 58"
        )

        assert result["status"] == "success"
        assert "message" in result

    def test_log_decision_all_phases(self):
        """Should accept all valid phases."""
        phases = ["pre_market", "planning", "execution", "monitoring", "eod"]

        for phase in phases:
            result = log_decision(
                phase=phase,
                action_type="analysis",
                summary=f"Test decision for {phase}",
                reasoning="Testing phase logging"
            )
            assert result["status"] == "success"

    def test_log_decision_all_action_types(self):
        """Should accept all valid action types."""
        action_types = [
            "analysis", "stock_selection", "trade_entry",
            "trade_exit", "monitoring", "skip"
        ]

        for action_type in action_types:
            result = log_decision(
                phase="execution",
                action_type=action_type,
                summary=f"Test {action_type} action",
                reasoning="Testing action type logging"
            )
            assert result["status"] == "success"

    def test_log_decision_with_symbol(self):
        """Should log decision with stock symbol."""
        result = log_decision(
            phase="execution",
            action_type="trade_entry",
            summary="Entered RELIANCE call option",
            reasoning="Strong breakout with volume confirmation",
            symbol="RELIANCE"
        )

        assert result["status"] == "success"
        assert "RELIANCE" in result["message"] or "Decision logged" in result["message"]

    def test_log_decision_with_data_points(self):
        """Should store structured data points as JSON."""
        import json

        data = {
            "entry_price": 45.50,
            "stop_loss": 42.00,
            "target": 50.00,
            "rsi": 62.5,
            "volume_surge": "2.5x"
        }

        result = log_decision(
            phase="execution",
            action_type="trade_entry",
            summary="SBIN call entry",
            reasoning="Technical breakout setup",
            symbol="SBIN",
            data_points=json.dumps(data)
        )

        assert result["status"] == "success"

    def test_log_decision_with_outcome(self):
        """Should log decision with outcome."""
        result = log_decision(
            phase="monitoring",
            action_type="trade_exit",
            summary="Exited HDFCBANK at profit",
            reasoning="Target reached, booking profits",
            symbol="HDFCBANK",
            outcome="Target hit, +12% gain"
        )

        assert result["status"] == "success"

    def test_log_decision_market_level(self):
        """Should log market-level decisions without symbol."""
        result = log_decision(
            phase="pre_market",
            action_type="analysis",
            summary="Market regime: Bullish trending",
            reasoning="Nifty above all major moving averages, sector rotation positive",
            data_points='{"nifty_rsi": 58, "banknifty_rsi": 62}'
        )

        assert result["status"] == "success"

    def test_log_decision_skip_action(self):
        """Should log skip decisions when no trade is taken."""
        result = log_decision(
            phase="execution",
            action_type="skip",
            summary="No trades today - choppy market",
            reasoning="Low conviction, sideways movement, waiting for clear setup"
        )

        assert result["status"] == "success"

    def test_log_decision_eod_summary(self):
        """Should log end-of-day summary."""
        result = log_decision(
            phase="eod",
            action_type="analysis",
            summary="Day summary: 2 trades, 1 winner 1 loser",
            reasoning="Market was volatile, profit booking was correct decision",
            outcome="Net PnL: +150"
        )

        assert result["status"] == "success"

    def test_log_decision_persistence(self):
        """Logged decisions should persist in database."""
        today = date.today().isoformat()

        # Log a decision
        log_result = log_decision(
            phase="execution",
            action_type="trade_entry",
            summary="Test persistence",
            reasoning="Testing database persistence",
            symbol="TESTSTOCK"
        )

        assert log_result["status"] == "success"

        # Verify it's in database
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT COUNT(*) FROM decision_log WHERE trade_date = ? AND summary = ?",
            [today, "Test persistence"]
        ).fetchone()

        assert rows[0] >= 1

    def test_log_multiple_decisions_same_phase(self):
        """Should allow multiple decisions in same phase."""
        for i in range(3):
            result = log_decision(
                phase="monitoring",
                action_type="monitoring",
                summary=f"Position check #{i+1}",
                reasoning=f"Monitoring open position - update {i+1}"
            )
            assert result["status"] == "success"

    def test_log_decision_with_empty_optional_fields(self):
        """Should handle empty optional fields gracefully."""
        result = log_decision(
            phase="planning",
            action_type="stock_selection",
            summary="Selected INFY for watchlist",
            reasoning="Good technical setup",
            symbol="",  # Empty symbol
            data_points="",  # Empty data points
            outcome=""  # Empty outcome
        )

        assert result["status"] == "success"

    def test_log_decision_complete_workflow(self):
        """Should log a complete trading workflow."""
        symbol = "WIPRO"

        # Pre-market analysis
        result1 = log_decision(
            phase="pre_market",
            action_type="analysis",
            summary="Market showing strength",
            reasoning="Gap up opening expected"
        )
        assert result1["status"] == "success"

        # Stock selection
        result2 = log_decision(
            phase="planning",
            action_type="stock_selection",
            summary=f"Selected {symbol}",
            reasoning="IT sector outperforming",
            symbol=symbol
        )
        assert result2["status"] == "success"

        # Trade entry
        result3 = log_decision(
            phase="execution",
            action_type="trade_entry",
            summary=f"Entered {symbol} call",
            reasoning="Breakout confirmed",
            symbol=symbol,
            data_points='{"entry": 40.0, "sl": 37.0}'
        )
        assert result3["status"] == "success"

        # Trade exit
        result4 = log_decision(
            phase="execution",
            action_type="trade_exit",
            summary=f"Exited {symbol} call",
            reasoning="Target reached",
            symbol=symbol,
            outcome="Profit: +250"
        )
        assert result4["status"] == "success"

        # EOD summary
        result5 = log_decision(
            phase="eod",
            action_type="analysis",
            summary="Day completed successfully",
            reasoning="1 trade, 1 winner",
            outcome="Daily PnL: +250"
        )
        assert result5["status"] == "success"

    def test_log_decision_retrieval(self):
        """Should be able to retrieve logged decisions."""
        today = date.today().isoformat()

        # Log a unique decision
        unique_summary = f"Unique test decision {date.today()}"
        log_decision(
            phase="execution",
            action_type="trade_entry",
            summary=unique_summary,
            reasoning="Test retrieval",
            symbol="RETRIEVE_TEST"
        )

        # Query database
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT phase, action_type, symbol, summary
            FROM decision_log
            WHERE trade_date = ? AND summary = ?
            """,
            [today, unique_summary]
        ).fetchone()

        assert result is not None
        assert result[0] == "execution"
        assert result[1] == "trade_entry"
        assert result[2] == "RETRIEVE_TEST"
        assert result[3] == unique_summary
