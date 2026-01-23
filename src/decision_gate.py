​You​
def decision_gate(regime: str) -> dict:
    """
    Maps market regime to trading behavior.
    Returns position sizing and permission flags.
    """

    if regime == "TREND":
        return {
            "allow_trade": True,
            "position_size": 1.0,
            "note": "Trend regime: full risk allowed"
        }

    elif regime == "RANGE":
        return {
            "allow_trade": True,
            "position_size": 0.5,
            "note": "Range regime: reduced size"
        }

    elif regime == "VOLATILE":
        return {
            "allow_trade": False,
            "position_size": 0.0,
            "note": "Volatile regime: trading disabled"
        }

    else:
        return {
            "allow_trade": False,
            "position_size": 0.0,
            "note": "Uncertain regime: no trade"
        }
