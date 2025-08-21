import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime
import os

# Мокаем FERNET_KEY для тестов (32 байта в base64)
os.environ["FERNET_KEY"] = "dGVzdC1mZXJuZXQta2V5LWZvci10ZXN0aW5nLW9ubHk="

from services.strategy_parameters import StrategyParameters
from models.trade_models import Deal
from schemas.deal import DealCreate


@pytest.fixture
def fake_user_id():
    return str(uuid4())

@pytest.fixture
def fake_bot_id():
    return str(uuid4())

@pytest.fixture
def sample_strategy_params():
    return {
        "ema_fast": 10,
        "ema_slow": 30,
        "risk_pct": 0.05,
        "entry_pct": 0.9,
        "trend_threshold": 0.001,
        "deposit_prct": 0.05,
        "stop_loss_pct": 0.02
    }

@pytest.fixture
def strategy_parameters():
    return StrategyParameters({
        "ema_fast": 10,
        "ema_slow": 30,
        "trend_threshold": 0.001,
        "deposit_prct": 0.05,
        "stop_loss_pct": 0.02
    })

@pytest.fixture
def fake_market_data():
    return {
        "close": [31000, 31200, 31100, 30900, 31300, 31400],
        "open": [30950, 31050, 31120, 30850, 31250, 31390],
        "high": [31200, 31250, 31200, 31000, 31400, 31500],
        "low":  [30900, 31000, 31090, 30800, 31200, 31300],
        "volume": [120, 115, 130, 140, 112, 123],
    }

@pytest.fixture
def market_data_df():
    return pd.DataFrame({
        'open': [50000, 50100, 50200, 50300, 50400],
        'high': [50100, 50200, 50300, 50400, 50500],
        'low': [49900, 50000, 50100, 50200, 50300],
        'close': [50100, 50200, 50300, 50400, 50500],
        'volume': [100, 110, 120, 130, 140]
    })

@pytest.fixture
def uptrend_data():
    np.random.seed(42)
    base_price = 50000
    trend = np.linspace(0, 1000, 50)
    noise = np.random.normal(0, 100, 50)
    prices = base_price + trend + noise
    
    return pd.DataFrame({
        'open': prices - 50,
        'high': prices + 100,
        'low': prices - 100,
        'close': prices,
        'volume': np.random.randint(100, 200, 50)
    })

@pytest.fixture
def downtrend_data():
    np.random.seed(42)
    base_price = 50000
    trend = np.linspace(0, -1000, 50)
    noise = np.random.normal(0, 100, 50)
    prices = base_price + trend + noise
    
    return pd.DataFrame({
        'open': prices - 50,
        'high': prices + 100,
        'low': prices - 100,
        'close': prices,
        'volume': np.random.randint(100, 200, 50)
    })

@pytest.fixture
def sideways_data():
    np.random.seed(42)
    base_price = 50000
    noise = np.random.normal(0, 50, 50)
    prices = base_price + noise
    
    return pd.DataFrame({
        'open': prices - 25,
        'high': prices + 50,
        'low': prices - 50,
        'close': prices,
        'volume': np.random.randint(100, 200, 50)
    })

@pytest.fixture
def mock_binance_client():
    from unittest.mock import MagicMock
    class MockBinanceClient:
        def get_balance(self, *args, **kwargs):
            return 1000
        def place_order(self, symbol, side, amount):
            return {"order_id": 1, "status": "filled"}
        def get_klines(self, symbol, interval, limit):
            return [
                [1640995200000, "50000", "50100", "49900", "50050", "100", 1640995259999, "5000000", 50, "50", "2500000", "0"],
                [1640995260000, "50050", "50200", "50000", "50150", "110", 1640995319999, "5510000", 55, "55", "2755000", "0"],
            ]
        def get_mark_price(self, symbol):
            return {"symbol": symbol, "markPrice": "50000.00"}
    return MockBinanceClient()

@pytest.fixture
def mock_db_session():
    return AsyncMock()

@pytest.fixture
def mock_deal_repository():
    return AsyncMock()

@pytest.fixture
def mock_apikeys_service():
    return AsyncMock()

@pytest.fixture
def mock_log_service():
    return AsyncMock()

@pytest.fixture
def mock_marketdata_service():
    return AsyncMock()

@pytest.fixture
def mock_balance_service():
    return AsyncMock()

@pytest.fixture
def mock_order_service():
    return AsyncMock()

@pytest.fixture
def mock_bot_service():
    return AsyncMock()

@pytest.fixture
def mock_exchange_client_factory():
    return MagicMock()

@pytest.fixture
def sample_deal():
    return Deal(
        id=1,
        user_id=uuid4(),
        bot_id=1,
        symbol="BTCUSDT",
        side="long",
        entry_price=50000.0,
        size=0.001,
        stop_loss=49000.0,
        status="open",
        template_id=1,
        opened_at=datetime.now()
    )

@pytest.fixture
def sample_deal_create_data():
    return DealCreate(
        user_id=uuid4(),
        bot_id=1,
        template_id=1,
        symbol="BTCUSDT",
        side="long",
        entry_price=50000.0,
        size=0.001,
        stop_loss=49000.0,
        status="open"
    )

@pytest.fixture
def sample_api_keys():
    return ("test-api-key", "test-api-secret")

@pytest.fixture
def sample_strategy_template():
    return MagicMock(
        user_id="test-user-123",
        symbol="BTCUSDT",
        parameters={
            "ema_fast": 10,
            "ema_slow": 30,
            "deposit_prct": 0.05,
            "trend_threshold": 0.001,
            "stop_loss_pct": 0.02
        },
        strategy_config_id=1
    )

@pytest.fixture
def sample_strategy_config():
    return MagicMock(
        id=1,
        name="NovichokStrategy",
        parameters={
            "ema_fast": 10,
            "ema_slow": 30,
            "deposit_prct": 0.05,
            "trend_threshold": 0.001,
            "stop_loss_pct": 0.02
        }
    )

@pytest.fixture
def sample_order_result():
    return {
        "order_id": "test-order-123",
        "status": "filled",
        "price": 50000.0,
        "quantity": 0.001,
        "symbol": "BTCUSDT"
    }

@pytest.fixture
def sample_strategy_log():
    return {
        "id": 1,
        "user_id": "test-user-123",
        "deal_id": 1,
        "message": "Test log message",
        "timestamp": datetime.now(),
        "level": "INFO"
    }

@pytest.fixture(scope="session")
def test_settings():
    return {
        "database_url": "postgresql://test:test@localhost:5432/test_db",
        "redis_url": "redis://localhost:6379/1",
        "binance_api_url": "https://testnet.binance.vision",
        "test_mode": True
    }

@pytest.fixture(autouse=True)
def cleanup_test_data():
    yield
    pass
