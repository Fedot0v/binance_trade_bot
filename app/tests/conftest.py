import pytest
from uuid import uuid4

# Фикстура для поддельного user_id (UUID)
@pytest.fixture
def fake_user_id():
    return uuid4()

# Фикстура для примерных параметров стратегии
@pytest.fixture
def sample_strategy_params():
    return {
        "ema_fast": 10,
        "ema_slow": 30,
        "risk_pct": 0.05,
        "entry_pct": 0.9
    }

# Фикстура для market data
@pytest.fixture
def fake_market_data():
    return {
        "close": [31000, 31200, 31100, 30900, 31300, 31400],
        "open": [30950, 31050, 31120, 30850, 31250, 31390],
        "high": [31200, 31250, 31200, 31000, 31400, 31500],
        "low":  [30900, 31000, 31090, 30800, 31200, 31300],
        "volume": [120, 115, 130, 140, 112, 123],
    }

# Фикстура для фейкового Binance-клиента (используется в других тестах)
@pytest.fixture
def mock_binance_client():
    from unittest.mock import MagicMock
    class MockBinanceClient:
        def get_balance(self, *args, **kwargs):
            return 1000
        def place_order(self, symbol, side, amount):
            return {"order_id": 1, "status": "filled"}
    return MockBinanceClient()
