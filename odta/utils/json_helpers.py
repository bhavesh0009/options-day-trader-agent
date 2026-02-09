"""JSON serialization helpers for DuckDB query results."""

from decimal import Decimal
from datetime import date, datetime


def convert_to_json_serializable(value):
    """Convert non-JSON-serializable types to JSON-safe values.

    Args:
        value: Any value from a database query or calculation.

    Returns:
        JSON-serializable version of the value.
    """
    if isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, (date, datetime)):
        return value.isoformat()
    elif value is None:
        return None
    return value


def convert_row_to_dict(row, columns):
    """Convert a database row to a JSON-serializable dict.

    Args:
        row: Database row tuple/list.
        columns: List of column names.

    Returns:
        Dictionary with column names as keys and JSON-safe values.
    """
    return {k: convert_to_json_serializable(v) for k, v in zip(columns, row)}


def convert_rows_to_dicts(rows, columns):
    """Convert multiple database rows to JSON-serializable dicts.

    Args:
        rows: List of database row tuples/lists.
        columns: List of column names.

    Returns:
        List of dictionaries with JSON-safe values.
    """
    return [convert_row_to_dict(row, columns) for row in rows]
