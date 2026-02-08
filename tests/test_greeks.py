from odta.tools.greeks import calculate_greeks


def test_call_greeks_calculation():
    """Greeks calculator should return valid delta/gamma/theta/vega for a call option."""
    result = calculate_greeks(
        spot_price=2450, strike_price=2500, expiry_days=10,
        option_premium=45, option_type="CE",
    )
    assert result["status"] == "success"
    assert 0 < result["delta"] < 1  # Call delta is between 0 and 1
    assert result["gamma"] > 0
    assert result["theta"] < 0  # Theta is negative (time decay)
    assert result["vega"] > 0
    assert result["iv"] > 0


def test_put_greeks_calculation():
    """Greeks calculator should return negative delta for a put option."""
    result = calculate_greeks(
        spot_price=2450, strike_price=2400, expiry_days=10,
        option_premium=30, option_type="PE",
    )
    assert result["status"] == "success"
    assert -1 < result["delta"] < 0  # Put delta is between -1 and 0


def test_implied_volatility_converges():
    """IV calculation should converge to a reasonable value."""
    result = calculate_greeks(
        spot_price=1000, strike_price=1000, expiry_days=30,
        option_premium=40, option_type="CE",
    )
    assert result["status"] == "success"
    assert 0.01 < result["iv"] < 2.0  # Reasonable IV range
