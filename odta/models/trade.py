from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class Trade(BaseModel):
    trade_date: date
    symbol: str
    option_symbol: str
    direction: str  # BUY_CE / BUY_PE
    entry_price: float
    exit_price: Optional[float] = None
    quantity: int
    pnl: Optional[float] = None
    entry_rationale: str = ""
    exit_rationale: str = ""
    market_conditions: str = ""
    learnings: str = ""
    mistakes: str = ""
    tags: str = ""


class Position(BaseModel):
    symbol: str
    option_symbol: str
    transaction_type: str  # BUY / SELL
    quantity: int
    entry_price: float
    entry_time: datetime
    status: str = "OPEN"  # OPEN / CLOSED
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None


class Order(BaseModel):
    order_id: str
    symbol: str
    option_symbol: str
    transaction_type: str
    quantity: int
    price: float
    order_type: str  # LIMIT / MARKET
    status: str  # PLACED / EXECUTED / REJECTED / CANCELLED
