import pandas_ta as ta
from odta.db.connection import get_db_connection


def get_market_regime(index: str = "NIFTY") -> dict:
    """Assess overall market direction and regime for Nifty or BankNifty.

    Analyzes recent daily data to classify the market as bullish/bearish/sideways
    and trending/ranging/volatile. Essential context before any stock-level analysis.

    For financial sector stocks, also check BankNifty.

    Args:
        index: "NIFTY" or "BANKNIFTY"

    Returns:
        dict with trend, regime, key_levels, recent_performance, and indicators
    """
    conn = get_db_connection()
    index_map = {"NIFTY": "NIFTY 50", "BANKNIFTY": "NIFTY BANK"}
    index_name = index_map.get(index.upper(), index)

    df = conn.execute(
        """
        SELECT date, open, high, low, close
        FROM index_ohlcv WHERE index_name = ?
        ORDER BY date DESC LIMIT 50
    """,
        [index_name],
    ).fetchdf()

    if df.empty:
        return {"status": "error", "reason": f"No data for index: {index}"}

    df = df.sort_values("date").reset_index(drop=True)

    sma_20 = df["close"].rolling(20).mean().iloc[-1]
    sma_50 = df["close"].rolling(50).mean().iloc[-1] if len(df) >= 50 else None
    rsi = ta.rsi(df["close"], length=14).iloc[-1]
    atr = ta.atr(df["high"], df["low"], df["close"], length=14).iloc[-1]
    current = df["close"].iloc[-1]

    # Trend classification
    if current > sma_20 and (sma_50 is None or sma_20 > sma_50):
        trend = "bullish"
    elif current < sma_20 and (sma_50 is None or sma_20 < sma_50):
        trend = "bearish"
    else:
        trend = "sideways"

    # Regime classification
    recent_atr = ta.atr(df["high"], df["low"], df["close"], length=5).iloc[-1]
    if recent_atr > atr * 1.3:
        regime = "volatile"
    elif abs(current - sma_20) / current < 0.01:
        regime = "ranging"
    else:
        regime = "trending"

    recent_high = df["high"].tail(20).max()
    recent_low = df["low"].tail(20).min()

    five_day_change = None
    if len(df) >= 6:
        five_day_change = round(
            (current - df["close"].iloc[-6]) / df["close"].iloc[-6] * 100, 2
        )

    return {
        "status": "success",
        "index": index,
        "current_price": round(float(current), 2),
        "trend": trend,
        "regime": regime,
        "rsi": round(float(rsi), 2),
        "sma_20": round(float(sma_20), 2),
        "sma_50": round(float(sma_50), 2) if sma_50 is not None else None,
        "atr_14": round(float(atr), 2),
        "key_levels": {
            "resistance": round(float(recent_high), 2),
            "support": round(float(recent_low), 2),
        },
        "5d_change_pct": five_day_change,
    }


def get_sector_sentiment(sector: str) -> dict:
    """Get sentiment for a specific sector by analyzing its constituent stocks.

    Args:
        sector: Sector name (e.g., "Banking", "IT", "Auto", "Pharma")

    Returns:
        dict with top gainers, losers, and sector trend assessment
    """
    conn = get_db_connection()

    stocks = conn.execute(
        """
        SELECT f.symbol, o.close, o.open,
               ROUND((o.close - o.open) / o.open * 100, 2) as day_change_pct
        FROM fno_stocks f
        JOIN daily_ohlcv o ON f.symbol = o.symbol
        WHERE f.sector = ? AND o.date = (SELECT MAX(date) FROM daily_ohlcv)
        ORDER BY day_change_pct DESC
    """,
        [sector],
    ).fetchall()

    if not stocks:
        return {"status": "error", "reason": f"No stocks found for sector: {sector}"}

    gainers = [{"symbol": s[0], "change": f"{s[3]}%"} for s in stocks if s[3] and s[3] > 0][:3]
    losers = [{"symbol": s[0], "change": f"{s[3]}%"} for s in stocks if s[3] and s[3] < 0][-3:]
    changes = [s[3] for s in stocks if s[3] is not None]
    avg_change = sum(changes) / len(changes) if changes else 0

    if avg_change > 0.5:
        trend = "bullish"
    elif avg_change < -0.5:
        trend = "bearish"
    else:
        trend = "neutral"

    return {
        "status": "success",
        "sector": sector,
        "sector_trend": trend,
        "avg_change_pct": round(avg_change, 2),
        "top_gainers": gainers,
        "top_losers": losers,
        "stock_count": len(stocks),
    }
