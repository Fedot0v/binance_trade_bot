# Тестирование Binance Trade Bot

Этот документ описывает систему тестирования для проекта Binance Trade Bot.

## Структура тестов

```
app/tests/
├── conftest.py              # Общие фикстуры и настройки
├── test_deal_service.py     # Тесты сервиса сделок
├── test_trade_service.py    # Тесты торгового сервиса
├── test_strategies.py       # Тесты торговых стратегий
├── test_integration.py      # Интеграционные тесты
├── test_api_routes.py       # Тесты API роутов
├── test_novichok_strategy.py # Тесты стратегии Novichok
├── test_paper_trading.py    # Тесты бумажной торговли
├── test_trade_router.py     # Тесты торговых роутов
└── test_binance_client.py   # Тесты Binance клиента
```

## Типы тестов

### 1. Unit тесты
- **Назначение**: Тестирование отдельных функций и методов
- **Файлы**: `test_*.py` с префиксом `test_`
- **Маркер**: `@pytest.mark.unit`

### 2. Интеграционные тесты
- **Назначение**: Тестирование взаимодействия между компонентами
- **Файл**: `test_integration.py`
- **Маркер**: `@pytest.mark.integration`

### 3. API тесты
- **Назначение**: Тестирование HTTP API эндпоинтов
- **Файл**: `test_api_routes.py`
- **Маркер**: `@pytest.mark.api`

## Установка зависимостей для тестирования

```bash
pip install -r requirements-test.txt
```

## Запуск тестов

### Запуск всех тестов
```bash
pytest
```

### Запуск с подробным выводом
```bash
pytest -v
```

### Запуск с покрытием кода
```bash
pytest --cov=app --cov-report=html
```

### Запуск конкретного типа тестов
```bash
# Только unit тесты
pytest -m unit

# Только интеграционные тесты
pytest -m integration

# Только API тесты
pytest -m api
```

### Запуск конкретного файла
```bash
pytest app/tests/test_deal_service.py
```

### Запуск конкретного теста
```bash
pytest app/tests/test_deal_service.py::TestDealService::test_create_deal_success
```

## Конфигурация pytest

Основные настройки находятся в файле `pytest.ini`:

- **asyncio_mode**: `auto` - автоматическое определение асинхронных тестов
- **testpaths**: `app/tests` - директория с тестами
- **python_files**: `test_*.py` - паттерн файлов тестов
- **addopts**: дополнительные опции для запуска

## Фикстуры

Общие фикстуры определены в `conftest.py`:

### Основные фикстуры
- `fake_user_id()` - UUID пользователя для тестов
- `fake_bot_id()` - UUID бота для тестов
- `mock_db_session()` - мок сессии базы данных
- `sample_deal()` - образец сделки для тестов

### Фикстуры для стратегий
- `strategy_parameters()` - параметры стратегии
- `market_data_df()` - рыночные данные в формате DataFrame
- `uptrend_data()` - данные с восходящим трендом
- `downtrend_data()` - данные с нисходящим трендом
- `sideways_data()` - данные с боковым движением

### Фикстуры для сервисов
- `mock_deal_service()` - мок сервиса сделок
- `mock_trade_service()` - мок торгового сервиса
- `mock_binance_client()` - мок Binance клиента

## Моки и стабы

### Использование моков
```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_example():
    with patch('module.ClassName') as mock_class:
        mock_instance = AsyncMock()
        mock_class.return_value = mock_instance
        mock_instance.method.return_value = "expected_result"
        
        # Тестируемый код
        result = await some_function()
        
        # Проверки
        assert result == "expected_result"
        mock_instance.method.assert_called_once()
```

### Асинхронные моки
```python
@pytest.mark.asyncio
async def test_async_function():
    mock_service = AsyncMock()
    mock_service.async_method.return_value = "result"
    
    result = await async_function(mock_service)
    assert result == "result"
```

## Покрытие кода

### Генерация отчета о покрытии
```bash
pytest --cov=app --cov-report=html --cov-report=term-missing
```

### Минимальное покрытие
Проект настроен на минимальное покрытие 70%. Если покрытие ниже, тесты не пройдут.

### Просмотр отчета
После генерации HTML отчета, откройте `htmlcov/index.html` в браузере.

## Интеграционные тесты

### Тестирование торгового цикла
```python
@pytest.mark.asyncio
async def test_complete_trading_cycle():
    # Настройка моков всех сервисов
    # Выполнение полного торгового цикла
    # Проверка результатов
```

### Тестирование обработки ошибок
```python
@pytest.mark.asyncio
async def test_error_handling():
    # Симуляция ошибок
    # Проверка корректной обработки
```

## API тесты

### Использование TestClient
```python
from fastapi.testclient import TestClient

def test_api_endpoint():
    client = TestClient(app)
    response = client.get("/api/endpoint")
    assert response.status_code == 200
```

### Тестирование с моками
```python
def test_api_with_mocks():
    with patch('routes.module.Service') as mock_service:
        client = TestClient(app)
        response = client.post("/api/endpoint", json=data)
        assert response.status_code == 200
```

## Тестирование стратегий

### Тестирование сигналов
```python
def test_strategy_signal():
    strategy = NovichokStrategy(params)
    signal = strategy.generate_signal(market_data)
    assert signal in ['long', 'short', 'hold']
```

### Тестирование с разными типами данных
```python
def test_strategy_with_trends():
    strategy = NovichokStrategy(params)
    
    # Восходящий тренд
    signal = strategy.generate_signal(uptrend_data)
    assert signal == 'long'
    
    # Нисходящий тренд
    signal = strategy.generate_signal(downtrend_data)
    assert signal == 'short'
```

## Отладка тестов

### Запуск с отладчиком
```bash
pytest --pdb
```

### Подробный вывод
```bash
pytest -v -s
```

### Логирование
```bash
pytest --log-cli-level=DEBUG
```

## CI/CD интеграция

### GitHub Actions
```yaml
- name: Run tests
  run: |
    pip install -r requirements-test.txt
    pytest --cov=app --cov-report=xml
```

### GitLab CI
```yaml
test:
  script:
    - pip install -r requirements-test.txt
    - pytest --cov=app --cov-report=xml
```

## Лучшие практики

### 1. Именование тестов
- Используйте описательные имена: `test_create_deal_success`
- Группируйте связанные тесты в классы: `TestDealService`

### 2. Структура тестов
```python
def test_example():
    # Arrange - подготовка данных
    data = {"key": "value"}
    
    # Act - выполнение действия
    result = function(data)
    
    # Assert - проверка результата
    assert result == "expected"
```

### 3. Использование фикстур
- Переиспользуйте общие данные через фикстуры
- Избегайте дублирования кода

### 4. Моки
- Мокайте внешние зависимости
- Проверяйте вызовы моков
- Используйте `assert_called_once()` и `assert_called_with()`

### 5. Асинхронные тесты
- Используйте `@pytest.mark.asyncio`
- Мокайте асинхронные функции с `AsyncMock`

## Устранение неполадок

### Проблемы с импортами
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest
```

### Проблемы с базой данных
```bash
# Используйте тестовую БД
export DATABASE_URL="postgresql://test:test@localhost:5432/test_db"
pytest
```

### Проблемы с асинхронными тестами
```bash
pytest --asyncio-mode=auto
```

## Дополнительные инструменты

### Линтеры
```bash
# Форматирование кода
black app/

# Проверка стиля
flake8 app/

# Проверка типов
mypy app/
```

### Безопасность
```bash
# Проверка уязвимостей
safety check
```

### Производительность
```bash
# Бенчмарки
pytest --benchmark-only
``` 