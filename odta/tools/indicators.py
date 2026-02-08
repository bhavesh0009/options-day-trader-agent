import pandas as pd
import pandas_ta as ta
from odta.db.connection import get_db_connection


def calculate_indicator(
    symbol: str, indicator: str, period: int = 14, lookback_days: int = 100
) -> dict:
    """Calculate a technical indicator for a stock using historical daily data.

    Supported indicators: RSI, MACD, SMA, EMA, ATR, ADX, BBANDS (Bollinger Bands),
    SUPERTREND, STOCH (Stochastic), OBV, VWAP, and any indicator supported by pandas-ta.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE").
        indicator: Indicator name (e.g., "RSI", "MACD", "SMA").
        period: Period/length for the indicator (default 14).
        lookback_days: How many days of historical data to use (default 100).

    Returns:
        dict with indicator values for recent dates
    """
    conn = get_db_connection()
    df = conn.execute(
        """
        SELECT date, open, high, low, close, volume
        FROM daily_ohlcv
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT ?
    """,
        [symbol, lookback_days],
    ).fetchdf()

    if df.empty:
        return {"status": "error", "reason": f"No data found for {symbol}"}

    df = df.sort_values("date").reset_index(drop=True)

    indicator_upper = indicator.upper()
    try:
        if indicator_upper == "RSI":
            result = ta.rsi(df["close"], length=period)
        elif indicator_upper == "SMA":
            result = ta.sma(df["close"], length=period)
        elif indicator_upper == "EMA":
            result = ta.ema(df["close"], length=period)
        elif indicator_upper == "ATR":
            result = ta.atr(df["high"], df["low"], df["close"], length=period)
        elif indicator_upper == "ADX":
            result = ta.adx(df["high"], df["low"], df["close"], length=period)
        elif indicator_upper == "MACD":
            result = ta.macd(df["close"])
        elif indicator_upper == "BBANDS":
            result = ta.bbands(df["close"], length=period)
        elif indicator_upper == "SUPERTREND":
            result = ta.supertrend(df["high"], df["low"], df["close"], length=period)
        elif indicator_upper == "STOCH":
            result = ta.stoch(df["high"], df["low"], df["close"])
        elif indicator_upper == "OBV":
            result = ta.obv(df["close"], df["volume"])
        else:
            # Try generic pandas-ta
            strategy = ta.Strategy(
                name="custom", ta=[{"kind": indicator.lower(), "length": period}]
            )
            df.ta.strategy(strategy)
            result = df.iloc[:, 6:]  # columns after OHLCV

        if isinstance(result, pd.Series):
            result = result.to_frame()

        # Return last 10 values
        recent = pd.concat([df[["date", "close"]], result], axis=1).tail(10)
        # Convert date objects and NaN to serializable types
        records = recent.to_dict(orient="records")
        for record in records:
            for key, value in record.items():
                if isinstance(value, pd.Timestamp):
                    record[key] = str(value.date())
                elif hasattr(value, "date"):
                    record[key] = str(value)
                elif pd.isna(value):
                    record[key] = None

        return {
            "status": "success",
            "symbol": symbol,
            "indicator": indicator,
            "period": period,
            "values": records,
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
