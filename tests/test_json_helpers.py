"""Tests for JSON serialization helpers.

This module tests:
- Decimal to float conversion
- Date/datetime to ISO string conversion
- Database row to dict conversion
- Multiple rows conversion
- Edge cases and None handling
"""

import pytest
from decimal import Decimal
from datetime import date, datetime
from odta.utils.json_helpers import (
    convert_to_json_serializable,
    convert_row_to_dict,
    convert_rows_to_dicts
)


class TestConvertToJsonSerializable:
    """Test conversion of non-JSON-serializable types."""

    def test_convert_decimal_to_float(self):
        """Should convert Decimal to float."""
        value = Decimal("123.45")
        result = convert_to_json_serializable(value)

        assert isinstance(result, float)
        assert result == 123.45

    def test_convert_decimal_with_precision(self):
        """Should handle Decimals with high precision."""
        value = Decimal("123.456789")
        result = convert_to_json_serializable(value)

        assert isinstance(result, float)
        assert abs(result - 123.456789) < 0.000001

    def test_convert_date_to_iso_string(self):
        """Should convert date to ISO format string."""
        value = date(2025, 2, 8)
        result = convert_to_json_serializable(value)

        assert isinstance(result, str)
        assert result == "2025-02-08"

    def test_convert_datetime_to_iso_string(self):
        """Should convert datetime to ISO format string."""
        value = datetime(2025, 2, 8, 14, 30, 45)
        result = convert_to_json_serializable(value)

        assert isinstance(result, str)
        assert "2025-02-08" in result
        assert "14:30:45" in result

    def test_convert_none_returns_none(self):
        """Should return None for None input."""
        result = convert_to_json_serializable(None)

        assert result is None

    def test_convert_string_unchanged(self):
        """Should return strings unchanged."""
        value = "test string"
        result = convert_to_json_serializable(value)

        assert result == value
        assert isinstance(result, str)

    def test_convert_int_unchanged(self):
        """Should return integers unchanged."""
        value = 42
        result = convert_to_json_serializable(value)

        assert result == value
        assert isinstance(result, int)

    def test_convert_float_unchanged(self):
        """Should return floats unchanged."""
        value = 3.14
        result = convert_to_json_serializable(value)

        assert result == value
        assert isinstance(result, float)

    def test_convert_bool_unchanged(self):
        """Should return booleans unchanged."""
        result_true = convert_to_json_serializable(True)
        result_false = convert_to_json_serializable(False)

        assert result_true is True
        assert result_false is False

    def test_convert_zero_decimal(self):
        """Should handle zero Decimal correctly."""
        value = Decimal("0")
        result = convert_to_json_serializable(value)

        assert isinstance(result, float)
        assert result == 0.0

    def test_convert_negative_decimal(self):
        """Should handle negative Decimals."""
        value = Decimal("-123.45")
        result = convert_to_json_serializable(value)

        assert isinstance(result, float)
        assert result == -123.45


class TestConvertRowToDict:
    """Test converting database rows to dictionaries."""

    def test_convert_simple_row(self):
        """Should convert a simple row to dict."""
        row = ("RELIANCE", 2450.50, 1000000)
        columns = ["symbol", "price", "volume"]

        result = convert_row_to_dict(row, columns)

        assert isinstance(result, dict)
        assert result["symbol"] == "RELIANCE"
        assert result["price"] == 2450.50
        assert result["volume"] == 1000000

    def test_convert_row_with_decimal(self):
        """Should convert row with Decimal values."""
        row = ("SBIN", Decimal("600.75"), 500000)
        columns = ["symbol", "price", "volume"]

        result = convert_row_to_dict(row, columns)

        assert isinstance(result["price"], float)
        assert result["price"] == 600.75

    def test_convert_row_with_date(self):
        """Should convert row with date values."""
        row = ("INFY", date(2025, 2, 8), 1500.00)
        columns = ["symbol", "trade_date", "price"]

        result = convert_row_to_dict(row, columns)

        assert isinstance(result["trade_date"], str)
        assert result["trade_date"] == "2025-02-08"

    def test_convert_row_with_datetime(self):
        """Should convert row with datetime values."""
        row = ("TCS", datetime(2025, 2, 8, 10, 30, 0), 3500.00)
        columns = ["symbol", "timestamp", "price"]

        result = convert_row_to_dict(row, columns)

        assert isinstance(result["timestamp"], str)
        assert "2025-02-08" in result["timestamp"]

    def test_convert_row_with_none_values(self):
        """Should handle None values in rows."""
        row = ("HDFCBANK", None, 1600.00)
        columns = ["symbol", "sector", "price"]

        result = convert_row_to_dict(row, columns)

        assert result["sector"] is None
        assert result["symbol"] == "HDFCBANK"

    def test_convert_row_with_mixed_types(self):
        """Should handle rows with mixed data types."""
        row = (
            "TATAMOTORS",
            date(2025, 2, 8),
            Decimal("750.25"),
            1000000,
            None,
            "Auto"
        )
        columns = ["symbol", "date", "price", "volume", "notes", "sector"]

        result = convert_row_to_dict(row, columns)

        assert result["symbol"] == "TATAMOTORS"
        assert isinstance(result["date"], str)
        assert isinstance(result["price"], float)
        assert result["volume"] == 1000000
        assert result["notes"] is None
        assert result["sector"] == "Auto"

    def test_convert_empty_row(self):
        """Should handle empty row."""
        row = ()
        columns = []

        result = convert_row_to_dict(row, columns)

        assert result == {}

    def test_column_row_length_mismatch(self):
        """Should handle mismatched column and row lengths gracefully."""
        row = ("WIPRO", 450.00)
        columns = ["symbol", "price", "volume"]  # Extra column

        # Should zip and only use available values
        result = convert_row_to_dict(row, columns)

        assert "symbol" in result
        assert "price" in result
        # volume won't be in result as row doesn't have that value


class TestConvertRowsToDicts:
    """Test converting multiple database rows to dictionaries."""

    def test_convert_multiple_rows(self):
        """Should convert multiple rows to list of dicts."""
        rows = [
            ("RELIANCE", 2450.00, 1000000),
            ("SBIN", 600.00, 800000),
            ("INFY", 1500.00, 600000)
        ]
        columns = ["symbol", "price", "volume"]

        result = convert_rows_to_dicts(rows, columns)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(row, dict) for row in result)

        assert result[0]["symbol"] == "RELIANCE"
        assert result[1]["symbol"] == "SBIN"
        assert result[2]["symbol"] == "INFY"

    def test_convert_rows_with_decimals(self):
        """Should convert multiple rows with Decimals."""
        rows = [
            ("TCS", Decimal("3500.50")),
            ("WIPRO", Decimal("450.75"))
        ]
        columns = ["symbol", "price"]

        result = convert_rows_to_dicts(rows, columns)

        assert len(result) == 2
        assert isinstance(result[0]["price"], float)
        assert isinstance(result[1]["price"], float)
        assert result[0]["price"] == 3500.50

    def test_convert_rows_with_dates(self):
        """Should convert multiple rows with dates."""
        rows = [
            ("TRADE1", date(2025, 2, 8), 250.00),
            ("TRADE2", date(2025, 2, 7), -150.00)
        ]
        columns = ["trade_id", "trade_date", "pnl"]

        result = convert_rows_to_dicts(rows, columns)

        assert len(result) == 2
        assert isinstance(result[0]["trade_date"], str)
        assert result[0]["trade_date"] == "2025-02-08"
        assert result[1]["trade_date"] == "2025-02-07"

    def test_convert_empty_rows_list(self):
        """Should handle empty rows list."""
        rows = []
        columns = ["symbol", "price"]

        result = convert_rows_to_dicts(rows, columns)

        assert result == []
        assert isinstance(result, list)

    def test_convert_single_row(self):
        """Should handle single row in list."""
        rows = [("SINGLE", 100.00)]
        columns = ["symbol", "price"]

        result = convert_rows_to_dicts(rows, columns)

        assert len(result) == 1
        assert result[0]["symbol"] == "SINGLE"

    def test_convert_rows_preserves_order(self):
        """Should preserve row order in conversion."""
        rows = [
            ("FIRST", 1),
            ("SECOND", 2),
            ("THIRD", 3),
            ("FOURTH", 4)
        ]
        columns = ["name", "order"]

        result = convert_rows_to_dicts(rows, columns)

        assert result[0]["name"] == "FIRST"
        assert result[1]["name"] == "SECOND"
        assert result[2]["name"] == "THIRD"
        assert result[3]["name"] == "FOURTH"


class TestJsonHelpersIntegration:
    """Test JSON helpers with real database scenarios."""

    def test_trade_diary_result_serializable(self):
        """Trade diary results should be JSON serializable."""
        import json

        # Simulate trade diary row
        row = (
            date(2025, 2, 8),
            "RELIANCE",
            "RELIANCE25FEB2500CE",
            "BUY_CE",
            Decimal("45.50"),
            Decimal("52.00"),
            75,
            Decimal("487.50"),
            "Bullish breakout",
            "Target reached",
            "Learning note",
            None,
            "breakout,momentum"
        )

        columns = [
            "trade_date", "symbol", "option_symbol", "direction",
            "entry_price", "exit_price", "quantity", "pnl",
            "entry_rationale", "exit_rationale", "learnings",
            "mistakes", "tags"
        ]

        result = convert_row_to_dict(row, columns)

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None
        assert isinstance(json_str, str)

        # Should be deserializable
        parsed = json.loads(json_str)
        assert parsed["symbol"] == "RELIANCE"
        assert parsed["pnl"] == 487.50

    def test_market_data_result_serializable(self):
        """Market data with Decimals should be JSON serializable."""
        import json

        rows = [
            ("RELIANCE", Decimal("2450.50"), Decimal("2460.00"), 1000000),
            ("SBIN", Decimal("600.75"), Decimal("605.00"), 800000),
            ("INFY", Decimal("1500.25"), Decimal("1510.50"), 600000)
        ]
        columns = ["symbol", "open", "close", "volume"]

        result = convert_rows_to_dicts(rows, columns)

        # Should be JSON serializable
        json_str = json.dumps(result)
        assert json_str is not None

        # Verify deserialization
        parsed = json.loads(json_str)
        assert len(parsed) == 3
        assert parsed[0]["symbol"] == "RELIANCE"
        assert isinstance(parsed[0]["open"], float)
