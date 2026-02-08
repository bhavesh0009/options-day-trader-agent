from datetime import datetime, time
import pytz

IST = pytz.timezone("Asia/Kolkata")

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)
PRE_MARKET_START = time(8, 45)
SQUARE_OFF_TIME = time(15, 0)


def now_ist() -> datetime:
    return datetime.now(IST)


def is_market_open() -> bool:
    now = now_ist()
    current_time = now.time()
    weekday = now.weekday()
    if weekday >= 5:  # Saturday/Sunday
        return False
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def is_pre_market() -> bool:
    now = now_ist()
    current_time = now.time()
    weekday = now.weekday()
    if weekday >= 5:
        return False
    return PRE_MARKET_START <= current_time < MARKET_OPEN


def is_past_square_off() -> bool:
    return now_ist().time() >= SQUARE_OFF_TIME


def today_str() -> str:
    return now_ist().strftime("%Y-%m-%d")


def current_time_str() -> str:
    return now_ist().strftime("%H:%M")
