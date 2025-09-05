from strategies.novichok_strategy import NovichokStrategy
from strategies.compensation_strategy import CompensationStrategy


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
            "stop_loss_pct": 0.02,
            "trailing_stop_pct": 0.005
        },
        "is_active": True,
    },
    "compensation": {
        "cls": CompensationStrategy,
        "name": "CompensationStrategy",
        "description": "Шаблон стратегии 'Компенсация и реакция' - основной актив BTC, страховка ETH",
        "default_parameters": {
            "ema_fast": 10,
            "ema_slow": 30,
            "trend_threshold": 0.001,
            "btc_deposit_prct": 0.05,
            "btc_stop_loss_pct": 0.012,
            "eth_deposit_prct": 0.1,
            "eth_stop_loss_pct": 0.01,
            "compensation_threshold": 0.0025,
            "compensation_time_window": 15,
            "impulse_threshold": 0.004,
            "candles_against_threshold": 2,
            "max_trade_duration": 60
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
