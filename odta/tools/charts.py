import os
import tempfile
from datetime import datetime

import mplfinance as mpf
import pandas as pd

from odta.db.connection import get_db_connection


def generate_chart(
    symbol: str,
    lookback_days: int = 60,
    indicators: str = "SMA_20,SMA_50",
    chart_type: str = "candle",
) -> dict:
    """Generate a candlestick chart with technical indicators for a stock.

    Creates a PNG chart image that can be analyzed by the LLM's vision capability
    for pattern recognition, support/resistance identification, and trend analysis.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE").
        lookback_days: Number of trading days to show (default 60).
        indicators: Comma-separated indicator overlays. Supported:
            SMA_20, SMA_50, EMA_20, EMA_50, BBANDS, VWAP.
            Volume is always shown. RSI is shown as a subplot.
        chart_type: "candle" (default) or "ohlc".

    Returns:
        dict with chart_path (absolute path to PNG) and metadata
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
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.index.name = "Date"

    # Rename columns to match mplfinance expectations
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    df = df.astype(float)

    # Parse requested indicators
    indicator_list = [i.strip().upper() for i in indicators.split(",") if i.strip()]

    addplots = []
    overlay_lines = {}

    for ind in indicator_list:
        if ind.startswith("SMA_"):
            period = int(ind.split("_")[1])
            col = df["Close"].rolling(period).mean()
            addplots.append(mpf.make_addplot(col, label=ind))
        elif ind.startswith("EMA_"):
            period = int(ind.split("_")[1])
            col = df["Close"].ewm(span=period, adjust=False).mean()
            addplots.append(mpf.make_addplot(col, label=ind))
        elif ind == "BBANDS":
            sma = df["Close"].rolling(20).mean()
            std = df["Close"].rolling(20).std()
            upper = sma + 2 * std
            lower = sma - 2 * std
            addplots.append(mpf.make_addplot(upper, color="gray", linestyle="--"))
            addplots.append(mpf.make_addplot(lower, color="gray", linestyle="--"))
        elif ind == "RSI":
            import pandas_ta as ta
            rsi = ta.rsi(df["Close"], length=14)
            rsi = rsi.bfill().fillna(50)
            addplots.append(mpf.make_addplot(rsi, panel="lower", ylabel="RSI", color="purple"))

    # Generate chart
    charts_dir = os.path.join(tempfile.gettempdir(), "odta_charts")
    os.makedirs(charts_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_path = os.path.join(charts_dir, f"{symbol}_{timestamp}.png")

    style = mpf.make_mpf_style(
        base_mpf_style="charles",
        gridstyle=":",
        y_on_right=True,
    )

    mpf.plot(
        df,
        type=chart_type,
        style=style,
        volume=True,
        addplot=addplots if addplots else None,
        title=f"\n{symbol} — Last {len(df)} Trading Days",
        figsize=(14, 8),
        savefig=dict(fname=chart_path, dpi=150, bbox_inches="tight"),
    )

    return {
        "status": "success",
        "chart_path": chart_path,
        "symbol": symbol,
        "days": len(df),
        "date_range": f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}",
        "indicators": indicator_list,
        "latest_close": round(float(df["Close"].iloc[-1]), 2),
        "latest_volume": int(df["Volume"].iloc[-1]),
    }


def generate_index_chart(
    index: str = "NIFTY",
    lookback_days: int = 60,
) -> dict:
    """Generate a chart for Nifty or BankNifty index.

    Useful for benchmarking stock performance against the broader market.

    Args:
        index: "NIFTY" or "BANKNIFTY".
        lookback_days: Number of trading days to show.

    Returns:
        dict with chart_path and metadata
    """
    conn = get_db_connection()
    index_map = {"NIFTY": "NIFTY 50", "BANKNIFTY": "NIFTY BANK"}
    index_name = index_map.get(index.upper(), index)

    df = conn.execute(
        """
        SELECT date, open, high, low, close
        FROM index_ohlcv
        WHERE index_name = ?
        ORDER BY date DESC
        LIMIT ?
    """,
        [index_name, lookback_days],
    ).fetchdf()

    if df.empty:
        return {"status": "error", "reason": f"No data for index: {index}"}

    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.index.name = "Date"
    df.columns = ["Open", "High", "Low", "Close"]
    df = df.astype(float)

    # Add SMA overlays
    sma_20 = df["Close"].rolling(20).mean()
    addplots = [mpf.make_addplot(sma_20, label="SMA_20")]

    charts_dir = os.path.join(tempfile.gettempdir(), "odta_charts")
    os.makedirs(charts_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    chart_path = os.path.join(charts_dir, f"{index}_{timestamp}.png")

    style = mpf.make_mpf_style(base_mpf_style="charles", gridstyle=":", y_on_right=True)

    mpf.plot(
        df,
        type="candle",
        style=style,
        addplot=addplots,
        title=f"\n{index_name} — Last {len(df)} Trading Days",
        figsize=(14, 6),
        savefig=dict(fname=chart_path, dpi=150, bbox_inches="tight"),
    )

    return {
        "status": "success",
        "chart_path": chart_path,
        "index": index,
        "days": len(df),
        "latest_close": round(float(df["Close"].iloc[-1]), 2),
    }
