from strategies.novichok_strategy import NovichokStrategy


REGISTRY = {
    "novichok": {
        "cls": NovichokStrategy,
        "name": "Novichok",
        "description": "EMA crossover with flat filter",
        "default_parameters": {
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.002,
            "deposit_prct": 0.10,
            "stop_loss_pct": 0.02
        },
        "is_active": True,
    },
}

def list_available():
    return [
        {
            "key": k, **{kk: vv for kk, vv in v.items() if kk != "cls"}
        }
        for k, v in REGISTRY.items()
    ]
