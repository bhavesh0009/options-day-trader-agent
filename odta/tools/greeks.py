import math
from scipy.stats import norm


def calculate_greeks(
    spot_price: float,
    strike_price: float,
    expiry_days: int,
    option_premium: float,
    option_type: str,
    risk_free_rate: float = 0.07,
) -> dict:
    """Calculate option Greeks (Delta, Gamma, Theta, Vega) and Implied Volatility.

    Uses Black-Scholes model. Useful for evaluating option pricing and risk.

    Args:
        spot_price: Current price of the underlying stock.
        strike_price: Strike price of the option.
        expiry_days: Number of calendar days until expiry.
        option_premium: Current market premium of the option.
        option_type: "CE" for Call, "PE" for Put.
        risk_free_rate: Annual risk-free rate (default 0.07 for India).

    Returns:
        dict with iv, delta, gamma, theta, vega values
    """
    T = max(expiry_days / 365.0, 0.001)
    is_call = option_type.upper() == "CE"

    # Newton-Raphson for IV
    iv = _implied_volatility(spot_price, strike_price, T, risk_free_rate, option_premium, is_call)

    # Greeks
    d1 = (math.log(spot_price / strike_price) + (risk_free_rate + 0.5 * iv**2) * T) / (
        iv * math.sqrt(T)
    )
    d2 = d1 - iv * math.sqrt(T)

    if is_call:
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1

    gamma = norm.pdf(d1) / (spot_price * iv * math.sqrt(T))
    vega = spot_price * norm.pdf(d1) * math.sqrt(T) / 100  # per 1% move in IV

    if is_call:
        theta = (
            -(spot_price * norm.pdf(d1) * iv) / (2 * math.sqrt(T))
            - risk_free_rate * strike_price * math.exp(-risk_free_rate * T) * norm.cdf(d2)
        ) / 365
    else:
        theta = (
            -(spot_price * norm.pdf(d1) * iv) / (2 * math.sqrt(T))
            + risk_free_rate * strike_price * math.exp(-risk_free_rate * T) * norm.cdf(-d2)
        ) / 365

    return {
        "status": "success",
        "iv": round(iv, 4),
        "iv_pct": f"{round(iv * 100, 2)}%",
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 2),
        "vega": round(vega, 2),
        "expiry_days": expiry_days,
    }


def _implied_volatility(S, K, T, r, market_price, is_call, max_iter=100, tol=1e-6):
    """Newton-Raphson method for implied volatility."""
    sigma = 0.3  # initial guess
    for _ in range(max_iter):
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if is_call:
            price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        vega = S * norm.pdf(d1) * math.sqrt(T)
        if vega < 1e-12:
            break
        sigma -= (price - market_price) / vega
        if abs(price - market_price) < tol:
            break
    return max(sigma, 0.01)
