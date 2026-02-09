from datetime import datetime

from odta.constants import (
    IST,
    MARKET_OPEN,
    MARKET_CLOSE,
    PRE_MARKET_START_TIME,
    SQUARE_OFF_TIME_OBJ,
    WEEKEND_START,
)


def now_ist() -> datetime:
    return datetime.now(IST)


def is_market_open() -> bool:
    now = now_ist()
    current_time = now.time()
    weekday = now.weekday()
    if weekday >= WEEKEND_START:  # Saturday/Sunday
        return False
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def is_pre_market() -> bool:
    now = now_ist()
    current_time = now.time()
    weekday = now.weekday()
    if weekday >= WEEKEND_START:
        return False
    return PRE_MARKET_START_TIME <= current_time < MARKET_OPEN


def is_past_square_off() -> bool:
    return now_ist().time() >= SQUARE_OFF_TIME_OBJ


def today_str() -> str:
    return now_ist().strftime("%Y-%m-%d")


def current_time_str() -> str:
    return now_ist().strftime("%H:%M")
