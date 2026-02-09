"""Tests for the odta.constants module.

Validates all constants, StateKeys class, and utility functions.
"""

from datetime import time
import pytz
import pytest

from odta.constants import (
    # Timezone constants
    IST_TIMEZONE_NAME,
    IST,
    # Time constants (objects)
    MARKET_OPEN,
    MARKET_CLOSE,
    PRE_MARKET_START_TIME,
    SQUARE_OFF_TIME_OBJ,
    # Time constants (strings)
    PRE_MARKET_START_STR,
    SQUARE_OFF_TIME_STR,
    # Guardrail defaults
    DEFAULT_MAX_DAILY_LOSS,
    DEFAULT_MAX_OPEN_POSITIONS,
    DEFAULT_MONITORING_INTERVAL,
    # Weekday constants
    SATURDAY,
    SUNDAY,
    WEEKEND_START,
    # StateKeys class
    StateKeys,
    # Utility functions
    parse_time_str,
    time_to_str,
)


class TestTimezoneConstants:
    """Test timezone-related constants."""

    def test_ist_timezone_name(self):
        """Verify IST timezone name is correct."""
        assert IST_TIMEZONE_NAME == "Asia/Kolkata"

    def test_ist_timezone_object(self):
        """Verify IST timezone object is properly initialized."""
        assert IST is not None
        assert isinstance(IST, pytz.tzinfo.BaseTzInfo)
        assert str(IST) == "Asia/Kolkata"


class TestTimeConstants:
    """Test time-related constants."""

    def test_market_open_time(self):
        """Verify market open time is 09:15."""
        assert MARKET_OPEN == time(9, 15)

    def test_market_close_time(self):
        """Verify market close time is 15:30."""
        assert MARKET_CLOSE == time(15, 30)

    def test_pre_market_start_time(self):
        """Verify pre-market start time is 08:45."""
        assert PRE_MARKET_START_TIME == time(8, 45)

    def test_square_off_time_obj(self):
        """Verify square-off time object is 15:00."""
        assert SQUARE_OFF_TIME_OBJ == time(15, 0)

    def test_pre_market_start_str(self):
        """Verify pre-market start string is '08:45'."""
        assert PRE_MARKET_START_STR == "08:45"

    def test_square_off_time_str(self):
        """Verify square-off time string is '15:00'."""
        assert SQUARE_OFF_TIME_STR == "15:00"

    def test_time_string_consistency(self):
        """Verify time strings match their time object equivalents."""
        # Parse strings and compare to time objects
        assert parse_time_str(PRE_MARKET_START_STR) == PRE_MARKET_START_TIME
        assert parse_time_str(SQUARE_OFF_TIME_STR) == SQUARE_OFF_TIME_OBJ

        # Convert time objects and compare to strings
        assert time_to_str(PRE_MARKET_START_TIME) == PRE_MARKET_START_STR
        assert time_to_str(SQUARE_OFF_TIME_OBJ) == SQUARE_OFF_TIME_STR


class TestGuardrailDefaults:
    """Test guardrail-related default constants."""

    def test_max_daily_loss(self):
        """Verify default max daily loss is 5000."""
        assert DEFAULT_MAX_DAILY_LOSS == 5000
        assert isinstance(DEFAULT_MAX_DAILY_LOSS, int)

    def test_max_open_positions(self):
        """Verify default max open positions is 2."""
        assert DEFAULT_MAX_OPEN_POSITIONS == 2
        assert isinstance(DEFAULT_MAX_OPEN_POSITIONS, int)

    def test_monitoring_interval(self):
        """Verify default monitoring interval is 120 seconds."""
        assert DEFAULT_MONITORING_INTERVAL == 120
        assert isinstance(DEFAULT_MONITORING_INTERVAL, int)


class TestWeekdayConstants:
    """Test weekday-related constants."""

    def test_saturday_constant(self):
        """Verify Saturday constant is 5."""
        assert SATURDAY == 5

    def test_sunday_constant(self):
        """Verify Sunday constant is 6."""
        assert SUNDAY == 6

    def test_weekend_start_constant(self):
        """Verify weekend starts at day 5 (Saturday)."""
        assert WEEKEND_START == 5
        assert WEEKEND_START == SATURDAY


class TestStateKeys:
    """Test StateKeys class for session state access."""

    def test_app_config_keys(self):
        """Verify app configuration keys have correct 'app:' prefix."""
        assert StateKeys.APP_MODE == "app:mode"
        assert StateKeys.APP_MAX_DAILY_LOSS == "app:max_daily_loss"
        assert StateKeys.APP_MAX_OPEN_POSITIONS == "app:max_open_positions"
        assert StateKeys.APP_SQUARE_OFF_TIME == "app:square_off_time"

    def test_runtime_state_keys(self):
        """Verify runtime state keys (no prefix)."""
        assert StateKeys.TRADE_DATE == "trade_date"
        assert StateKeys.DAILY_PNL == "daily_pnl"
        assert StateKeys.OPEN_POSITIONS_COUNT == "open_positions_count"
        assert StateKeys.MONITORING_INTERVAL == "monitoring_interval"
        assert StateKeys.PHASE == "phase"
        assert StateKeys.WATCHLIST == "watchlist"
        assert StateKeys.STOP_REASON == "stop_reason"

    def test_all_keys_are_strings(self):
        """Verify all StateKeys attributes are strings."""
        for attr_name in dir(StateKeys):
            if not attr_name.startswith("_"):  # Skip private attributes
                attr_value = getattr(StateKeys, attr_name)
                assert isinstance(attr_value, str), f"{attr_name} should be a string"

    def test_no_duplicate_keys(self):
        """Verify no duplicate key values in StateKeys."""
        keys = []
        for attr_name in dir(StateKeys):
            if not attr_name.startswith("_"):
                keys.append(getattr(StateKeys, attr_name))

        # Check for duplicates
        assert len(keys) == len(set(keys)), "StateKeys has duplicate values"


class TestParseTimeStr:
    """Test parse_time_str utility function."""

    def test_valid_time_strings(self):
        """Test parsing valid time strings."""
        assert parse_time_str("00:00") == time(0, 0)
        assert parse_time_str("08:45") == time(8, 45)
        assert parse_time_str("15:00") == time(15, 0)
        assert parse_time_str("23:59") == time(23, 59)

    def test_invalid_format_raises_error(self):
        """Test that invalid formats raise ValueError."""
        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_str("25:00")  # Invalid hour

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_str("12:60")  # Invalid minute

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_str("12-30")  # Wrong separator

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_str("12:30:45")  # Too many parts

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_time_str("noon")  # Not a time string

    def test_edge_cases(self):
        """Test edge cases for parse_time_str."""
        # Empty string
        with pytest.raises(ValueError):
            parse_time_str("")

        # None
        with pytest.raises(ValueError):
            parse_time_str(None)


class TestTimeToStr:
    """Test time_to_str utility function."""

    def test_valid_time_objects(self):
        """Test converting valid time objects to strings."""
        assert time_to_str(time(0, 0)) == "00:00"
        assert time_to_str(time(8, 45)) == "08:45"
        assert time_to_str(time(15, 0)) == "15:00"
        assert time_to_str(time(23, 59)) == "23:59"

    def test_zero_padding(self):
        """Test that hours and minutes are zero-padded."""
        assert time_to_str(time(1, 5)) == "01:05"
        assert time_to_str(time(9, 0)) == "09:00"

    def test_round_trip_conversion(self):
        """Test that parse and format are inverse operations."""
        test_times = ["00:00", "08:45", "12:30", "15:00", "23:59"]
        for time_str in test_times:
            time_obj = parse_time_str(time_str)
            converted_back = time_to_str(time_obj)
            assert converted_back == time_str


class TestConstantsIntegration:
    """Integration tests for constants usage."""

    def test_no_circular_imports(self):
        """Verify constants module can be imported without circular dependencies."""
        # This test passes if the module imports successfully
        import odta.constants

        assert odta.constants is not None

    def test_constants_used_by_other_modules(self):
        """Verify constants are importable and usable by other modules."""
        # Test that key modules can import constants
        from odta.utils.time_helpers import IST as time_helpers_IST
        from odta.models.config import (
            DEFAULT_MAX_DAILY_LOSS as config_max_loss,
        )

        # These should be the same objects/values
        assert time_helpers_IST is IST
        assert config_max_loss == DEFAULT_MAX_DAILY_LOSS

    def test_config_defaults_match_constants(self):
        """Verify config defaults use the same values as constants."""
        from odta.models.config import GuardrailsConfig

        config = GuardrailsConfig()

        # Verify defaults match constants
        assert config.max_daily_loss == DEFAULT_MAX_DAILY_LOSS
        assert config.max_open_positions == DEFAULT_MAX_OPEN_POSITIONS
        assert config.square_off_time == SQUARE_OFF_TIME_STR
        assert config.pre_market_start == PRE_MARKET_START_STR
