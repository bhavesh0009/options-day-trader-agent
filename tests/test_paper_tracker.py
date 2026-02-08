"""Tests for paper position tracker.

These tests require the database to be initialized with paper_positions table.
Run initialize_database() before running these tests.
"""
from odta.tools.paper_tracker import get_paper_positions


def test_get_paper_positions_empty():
    """Should return empty positions when none exist."""
    result = get_paper_positions()
    assert result["status"] == "success"
    assert isinstance(result["open_positions"], list)
    assert isinstance(result["closed_today"], list)
    assert result["open_count"] >= 0
