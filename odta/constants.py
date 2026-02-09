"""Centralized constants for the ODTA trading system.

This module serves as the single source of truth for all system-wide constants,
including timezone, trading hours, and default guardrail values.

Design Principles:
- All constants defined once here
- Type-specific constants for different use cases (str vs time objects)
- Import from this module, never hardcode values elsewhere
- Config.yaml overrides these defaults at runtime

Type Strategy for Time Values:
- String format ("15:00") - Used for config.yaml, session state, display, string comparisons
- time object (time(15,0)) - Used for datetime comparisons, time logic
- Constants with *_STR suffix are strings, *_TIME or *_OBJ suffix are time objects
"""

from datetime import time
import pytz


# ============================================================================
# TIMEZONE
# ============================================================================
IST_TIMEZONE_NAME = "Asia/Kolkata"
IST = pytz.timezone(IST_TIMEZONE_NAME)


# ============================================================================
# TRADING HOURS (time objects for comparison logic)
# ============================================================================
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
PRE_MARKET_START_TIME = time(8, 45)
SQUARE_OFF_TIME_OBJ = time(15, 0)


# ============================================================================
# TIME STRINGS (for config, display, and string comparisons)
# ============================================================================
PRE_MARKET_START_STR = "08:45"
SQUARE_OFF_TIME_STR = "15:00"


# ============================================================================
# GUARDRAIL DEFAULTS (overridable via config.yaml)
# ============================================================================
DEFAULT_MAX_DAILY_LOSS = 5000
DEFAULT_MAX_OPEN_POSITIONS = 2
DEFAULT_MONITORING_INTERVAL = 120  # seconds


# ============================================================================
# WEEKDAY CONSTANTS
# ============================================================================
SATURDAY = 5
SUNDAY = 6
WEEKEND_START = 5  # Saturday onwards


# ============================================================================
# SESSION STATE KEYS (for ADK session state access)
# ============================================================================
class StateKeys:
    """Namespaced keys for ADK session state.

    Provides type-safe access to session state keys with IDE autocomplete
    and compile-time validation. All session state access should use these
    keys instead of hardcoded strings.

    Categories:
    - APP_* - Application configuration values (injected from config.yaml)
    - Other keys - Runtime state updated by agents during execution
    """

    # App configuration (injected from config.yaml, prefixed with "app:")
    APP_MODE = "app:mode"  # str: "paper" or "live"
    APP_MAX_DAILY_LOSS = "app:max_daily_loss"  # int: Maximum daily loss in rupees
    APP_MAX_OPEN_POSITIONS = "app:max_open_positions"  # int: Maximum concurrent positions
    APP_SQUARE_OFF_TIME = "app:square_off_time"  # str: Time to square off (HH:MM format)

    # Runtime state (updated by agents during execution)
    TRADE_DATE = "trade_date"  # str: Current trading date (YYYY-MM-DD)
    DAILY_PNL = "daily_pnl"  # float: Current day's profit/loss in rupees
    OPEN_POSITIONS_COUNT = "open_positions_count"  # int: Number of currently open positions
    MONITORING_INTERVAL = "monitoring_interval"  # int: Sleep duration between checks (seconds)
    PHASE = "phase"  # str: Current trading phase (e.g., "pre_market", "trading", "eod")
    WATCHLIST = "watchlist"  # list[str] or str: Stocks being monitored
    STOP_REASON = "stop_reason"  # str: Reason why trading loop stopped


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def parse_time_str(time_str: str) -> time:
    """Parse HH:MM string to time object.

    Converts a time string in HH:MM format to a Python time object
    for use in datetime comparisons and time logic.

    Args:
        time_str: Time in HH:MM format (e.g., "15:00", "08:45")

    Returns:
        time object corresponding to the input string

    Raises:
        ValueError: If format is invalid or cannot be parsed

    Example:
        >>> parse_time_str("15:00")
        datetime.time(15, 0)
        >>> parse_time_str("08:45")
        datetime.time(8, 45)
    """
    try:
        hour, minute = time_str.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"Invalid time format: {time_str}. Expected HH:MM (e.g., '15:00')"
        ) from e


def time_to_str(time_obj: time) -> str:
    """Convert time object to HH:MM string.

    Converts a Python time object to a string in HH:MM format
    for use in config files, session state, and display.

    Args:
        time_obj: Python time object

    Returns:
        String in HH:MM format with zero-padded hours and minutes

    Example:
        >>> time_to_str(time(15, 0))
        '15:00'
        >>> time_to_str(time(8, 45))
        '08:45'
    """
    return time_obj.strftime("%H:%M")
