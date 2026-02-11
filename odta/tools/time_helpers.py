from datetime import datetime
from odta.constants import IST


def get_current_time() -> dict:
    """Get the current time in IST.

    Use this tool whenever you need to know the exact current time
    for your trading updates or decision-making.

    Returns:
        dict with current time in various formats
    """
    now = datetime.now(IST)

    return {
        "status": "success",
        "current_time": now.strftime("%H:%M IST"),
        "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S IST"),
        "hour": now.hour,
        "minute": now.minute,
        "timestamp": now.isoformat(),
    }
