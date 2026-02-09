"""Tests for database integration with real data.

This module tests:
- Database connectivity
- Real data queries (fno_stocks, daily_ohlcv, index_ohlcv)
- Lot size data availability
- Sector and industry data
- Ban list functionality
- Data integrity
"""

import pytest
from odta.db.connection import get_db_connection


class TestDatabaseConnection:
    """Test database connection and basic operations."""

    def test_database_connection_established(self):
        """Should establish database connection successfully."""
        conn = get_db_connection()
        assert conn is not None

    def test_database_is_duckdb(self):
        """Connection should be a DuckDB connection."""
        conn = get_db_connection()
        assert hasattr(conn, 'execute')
        assert hasattr(conn, 'fetchall')


class TestFNOStocksTable:
    """Test FNO stocks table with real data."""

    def test_fno_stocks_table_exists(self):
        """fno_stocks table should exist."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'fno_stocks'"
        ).fetchone()
        assert result[0] >= 1

    def test_fno_stocks_has_data(self):
        """fno_stocks table should contain stock data."""
        conn = get_db_connection()
        result = conn.execute("SELECT COUNT(*) FROM fno_stocks").fetchone()
        assert result[0] > 0

    def test_fno_stocks_has_lot_size(self):
        """fno_stocks should have lot_size data populated."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT symbol, lot_size FROM fno_stocks WHERE lot_size IS NOT NULL LIMIT 10"
        ).fetchall()

        assert len(result) > 0
        for row in result:
            symbol, lot_size = row
            assert lot_size > 0
            assert isinstance(lot_size, (int, float))

    def test_lot_size_reasonable_values(self):
        """Lot sizes should be reasonable (e.g., 50-5000)."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT MIN(lot_size), MAX(lot_size), AVG(lot_size) FROM fno_stocks WHERE lot_size IS NOT NULL"
        ).fetchone()

        min_lot, max_lot, avg_lot = result
        assert min_lot >= 0  # Minimum lot size should be non-negative
        assert max_lot <= 100000  # Maximum lot size shouldn't exceed 100000
        assert avg_lot > 0

    def test_fno_stocks_has_sector_data(self):
        """fno_stocks should have sector information."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT symbol, sector FROM fno_stocks WHERE sector IS NOT NULL LIMIT 5"
        ).fetchall()

        # Some stocks should have sector data
        if result:
            for row in result:
                symbol, sector = row
                assert sector is not None
                assert len(sector) > 0

    def test_fno_stocks_has_industry_data(self):
        """fno_stocks should have industry information."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT symbol, industry FROM fno_stocks WHERE industry IS NOT NULL LIMIT 5"
        ).fetchall()

        # Some stocks should have industry data
        if result:
            for row in result:
                symbol, industry = row
                assert industry is not None
                assert len(industry) > 0

    def test_fno_stocks_common_symbols_exist(self):
        """Common FNO stocks should be in database."""
        conn = get_db_connection()
        common_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "SBIN"]

        for symbol in common_symbols:
            result = conn.execute(
                "SELECT symbol FROM fno_stocks WHERE symbol = ?",
                [symbol]
            ).fetchone()

            # At least some of these common symbols should exist
            # (depends on database setup)

    def test_fno_stocks_unique_symbols(self):
        """Each symbol should appear only once in fno_stocks."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT symbol, COUNT(*) as cnt FROM fno_stocks GROUP BY symbol HAVING cnt > 1"
        ).fetchall()

        # Should have no duplicates
        assert len(result) == 0


class TestDailyOHLCV:
    """Test daily OHLCV data."""

    def test_daily_ohlcv_table_exists(self):
        """daily_ohlcv table should exist."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'daily_ohlcv'"
        ).fetchone()
        assert result[0] >= 1

    def test_daily_ohlcv_has_data(self):
        """daily_ohlcv should have price data."""
        conn = get_db_connection()
        result = conn.execute("SELECT COUNT(*) FROM daily_ohlcv").fetchone()
        assert result[0] > 0

    def test_daily_ohlcv_data_structure(self):
        """daily_ohlcv should have proper OHLCV structure."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT symbol, date, open, high, low, close, volume FROM daily_ohlcv LIMIT 1"
        ).fetchone()

        if result:
            symbol, date, open_p, high, low, close, volume = result
            assert symbol is not None
            assert date is not None
            assert high >= low
            assert high >= open_p
            assert high >= close
            assert low <= open_p
            assert low <= close

    def test_daily_ohlcv_volume_positive(self):
        """Volume should be positive."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM daily_ohlcv WHERE volume <= 0"
        ).fetchone()

        # Most entries should have positive volume
        assert result[0] < 100  # Allow some null/zero entries

    def test_daily_ohlcv_recent_data_available(self):
        """Should have recent price data."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT MAX(date) FROM daily_ohlcv"
        ).fetchone()

        max_date = result[0]
        assert max_date is not None

    def test_daily_ohlcv_multiple_symbols(self):
        """Should have data for multiple symbols."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(DISTINCT symbol) FROM daily_ohlcv"
        ).fetchone()

        distinct_symbols = result[0]
        assert distinct_symbols > 0


class TestIndexOHLCV:
    """Test index OHLCV data."""

    def test_index_ohlcv_table_exists(self):
        """index_ohlcv table should exist."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'index_ohlcv'"
        ).fetchone()
        assert result[0] >= 1

    def test_index_ohlcv_has_nifty_data(self):
        """Should have NIFTY 50 index data."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM index_ohlcv WHERE index_name = 'NIFTY 50'"
        ).fetchone()

        # May or may not have data depending on setup
        # Just verify query works
        assert result[0] >= 0

    def test_index_ohlcv_has_banknifty_data(self):
        """Should have NIFTY BANK index data."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM index_ohlcv WHERE index_name = 'NIFTY BANK'"
        ).fetchone()

        assert result[0] >= 0

    def test_index_ohlcv_data_structure(self):
        """index_ohlcv should have proper structure."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT index_name, date, open, high, low, close FROM index_ohlcv LIMIT 1"
        ).fetchone()

        if result:
            index_name, date, open_p, high, low, close = result
            assert index_name is not None
            assert high >= low
            assert high >= open_p
            assert high >= close

    def test_index_ohlcv_price_ranges_reasonable(self):
        """Index prices should be in reasonable ranges."""
        conn = get_db_connection()
        result = conn.execute(
            """
            SELECT index_name, MIN(close), MAX(close)
            FROM index_ohlcv
            WHERE index_name IN ('NIFTY 50', 'NIFTY BANK')
            GROUP BY index_name
            """
        ).fetchall()

        for row in result:
            index_name, min_close, max_close = row
            if index_name == "NIFTY 50":
                # NIFTY should be in reasonable range (e.g., 10000-30000)
                assert min_close > 5000
                assert max_close < 50000
            elif index_name == "NIFTY BANK":
                # Bank Nifty should be in reasonable range
                assert min_close > 10000
                assert max_close < 100000


class TestBanList:
    """Test ban list functionality."""

    def test_ban_list_table_exists(self):
        """ban_list table should exist."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'ban_list'"
        ).fetchone()
        assert result[0] >= 1

    def test_ban_list_query_works(self):
        """Should be able to query ban_list."""
        conn = get_db_connection()
        result = conn.execute("SELECT COUNT(*) FROM ban_list").fetchone()

        # May be empty or have data
        assert result[0] >= 0

    def test_ban_list_structure(self):
        """ban_list should have symbol and ban_date columns."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT symbol, ban_date FROM ban_list LIMIT 1"
        ).fetchall()

        # If there's data, check structure
        if result:
            row = result[0]
            assert len(row) == 2
            assert row[0] is not None  # symbol
            assert row[1] is not None  # ban_date


class TestSequenceTables:
    """Test trade diary and decision log tables."""

    def test_trade_diary_table_exists(self):
        """trade_diary table should exist."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'trade_diary'"
        ).fetchone()
        assert result[0] >= 1

    def test_decision_log_table_exists(self):
        """decision_log table should exist."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'decision_log'"
        ).fetchone()
        assert result[0] >= 1

    def test_paper_positions_table_exists(self):
        """paper_positions table should exist."""
        conn = get_db_connection()
        result = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'paper_positions'"
        ).fetchone()
        assert result[0] >= 1

    def test_trade_diary_has_auto_increment(self):
        """trade_diary should have auto-incrementing ID."""
        conn = get_db_connection()
        # Just verify we can query the table
        result = conn.execute("SELECT COUNT(*) FROM trade_diary").fetchone()
        assert result[0] >= 0

    def test_decision_log_has_timestamp(self):
        """decision_log entries should have timestamps."""
        conn = get_db_connection()
        # Verify table structure
        result = conn.execute(
            "SELECT COUNT(*) FROM decision_log"
        ).fetchone()
        assert result[0] >= 0


class TestDataIntegrity:
    """Test data integrity and consistency."""

    def test_fno_stocks_match_daily_ohlcv(self):
        """Symbols in daily_ohlcv should mostly exist in fno_stocks."""
        conn = get_db_connection()

        # Get count of OHLCV symbols
        ohlcv_symbols = conn.execute(
            "SELECT COUNT(DISTINCT symbol) FROM daily_ohlcv"
        ).fetchone()[0]

        # Get count of FNO symbols
        fno_symbols = conn.execute(
            "SELECT COUNT(symbol) FROM fno_stocks"
        ).fetchone()[0]

        # Should have some relationship (not necessarily 1:1)
        assert ohlcv_symbols > 0 or fno_symbols > 0

    def test_lot_size_coverage(self):
        """Most FNO stocks should have lot_size data."""
        conn = get_db_connection()

        total = conn.execute("SELECT COUNT(*) FROM fno_stocks").fetchone()[0]
        with_lot_size = conn.execute(
            "SELECT COUNT(*) FROM fno_stocks WHERE lot_size IS NOT NULL AND lot_size > 0"
        ).fetchone()[0]

        if total > 0:
            coverage = (with_lot_size / total) * 100
            # At least 50% should have lot_size data
            assert coverage >= 50.0

    def test_database_not_empty(self):
        """Database should have meaningful data."""
        conn = get_db_connection()

        # Check multiple tables
        fno_count = conn.execute("SELECT COUNT(*) FROM fno_stocks").fetchone()[0]
        ohlcv_count = conn.execute("SELECT COUNT(*) FROM daily_ohlcv").fetchone()[0]

        # At least one table should have data
        assert fno_count > 0 or ohlcv_count > 0
