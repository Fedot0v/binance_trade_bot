# Универсальный бектест стратегий

## Описание

Универсальный бектест-сервис позволяет тестировать любую стратегию из реестра на исторических данных. Система поддерживает:

- ✅ Выбор стратегии из реестра
- ✅ Скачивание данных с Binance API
- ✅ Загрузка CSV файлов
- ✅ Детальная статистика бектеста
- ✅ Следование принципам SOLID

## Архитектура

### Схемы (Schemas)
- `BacktestRequest` - запрос на запуск бектеста
- `BacktestResult` - результат бектеста
- `BacktestTrade` - информация о сделке
- `BacktestEquityPoint` - точка на кривой доходности
- `AvailableStrategy` - доступная стратегия

### Сервисы (Services)
- `BacktestService` - основной сервис бектеста
- `CSVDataService` - работа с CSV данными
- `BacktestStatisticsService` - расчет статистики

### Стратегии (Strategies)
Все стратегии наследуются от `BaseStrategy` и должны реализовывать:
- `generate_signal()` - генерация торгового сигнала
- `calculate_position_size()` - расчет размера позиции
- `calculate_stop_loss_price()` - стоп-лосс (опционально)
- `calculate_take_profit_price()` - тейк-профит (опционально)

## Использование

### 1. Через веб-интерфейс

1. Запустите приложение:
```bash
python -m app.main
```

2. Откройте http://localhost:8000/backtest/run/

3. Выберите:
   - Стратегию из списка
   - Источник данных (скачать с Binance или загрузить CSV)
   - Параметры (символ, даты, начальный баланс)

4. Нажмите "Запустить бектест"

### 2. Программно

```python
from app.services.backtest.backtest_service import BacktestService

# Создаем сервис
backtest_service = BacktestService()

# Запускаем бектест
result = await backtest_service.run_backtest(
    strategy_key="novichok",
    data_source="download",
    symbol="BTCUSDT",
    start_date="2024-01-01",
    end_date="2024-01-31",
    initial_balance=10000.0
)

# Анализируем результаты
print(f"Общий PnL: ${result.total_pnl:,.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Максимальная просадка: {result.max_drawdown_pct:.2f}%")
```

## Статистика бектеста

### Основные показатели
- **Общий PnL** - общая прибыль/убыток в долларах и процентах
- **Максимальная просадка** - максимальное падение баланса
- **Коэффициент Шарпа** - отношение доходности к волатильности

### Статистика сделок
- **Всего сделок** - общее количество сделок
- **Win Rate** - процент прибыльных сделок
- **Средняя прибыль/убыток** - средние значения по сделкам
- **Profit Factor** - отношение общей прибыли к общему убытку

## Добавление новой стратегии

1. Создайте класс стратегии, наследующий от `BaseStrategy`:

```python
from strategies.base_strategy import BaseStrategy
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self, config: dict):
        super().__init__(config)
        # Инициализация параметров
        
    def generate_signal(self, df: pd.DataFrame) -> str:
        # Логика генерации сигнала
        # Возвращает: 'long', 'short' или None
        pass
        
    def calculate_position_size(self, balance: float) -> float:
        # Расчет размера позиции в долларах
        return balance * self.config.get('risk_pct', 0.1)
```

2. Добавьте стратегию в реестр (`app/strategies/registry.py`):

```python
from strategies.my_strategy import MyStrategy

REGISTRY = {
    # ... существующие стратегии ...
    "my_strategy": {
        "cls": MyStrategy,
        "name": "My Strategy",
        "description": "Описание моей стратегии",
        "default_parameters": {
            "risk_pct": 0.1,
            "stop_loss_pct": 0.02,
            # другие параметры
        },
        "is_active": True,
    },
}
```

## Формат CSV данных

CSV файл должен содержать колонки:
- `timestamp` - время в миллисекундах
- `open` - цена открытия
- `high` - максимальная цена
- `low` - минимальная цена
- `close` - цена закрытия
- `volume` - объем

Пример:
```csv
timestamp,open,high,low,close,volume
1640995200000,46200.50,46300.00,46100.00,46250.25,1234.56
1640995260000,46250.25,46400.00,46200.00,46350.75,2345.67
```

## Источники данных

### Binance API
- Автоматическое скачивание исторических данных
- Поддерживаемые пары: BTCUSDT, ETHUSDT, ADAUSDT, DOTUSDT, LINKUSDT
- Интервал: 1 минута
- Лимит: до 1000 свечей за запрос

### CSV файлы
- Поддерживаются файлы с TradingView, cryptodatadownload.com, Kaggle
- Автоматическая валидация формата
- Конвертация timestamp в datetime

## Тестирование

Запустите тестовый скрипт:
```bash
python test_universal_backtest.py
```

Этот скрипт проверит:
- Импорт всех модулей
- Создание сервисов
- Получение списка стратегий
- Корректность схем данных

## Принципы SOLID

### Single Responsibility Principle
- `CSVDataService` - только работа с CSV
- `BacktestStatisticsService` - только расчет статистики
- `BacktestService` - координация процесса бектеста

### Open/Closed Principle
- Легко добавлять новые стратегии без изменения существующего кода
- Расширение функциональности через наследование

### Liskov Substitution Principle
- Все стратегии взаимозаменяемы через базовый класс
- Единый интерфейс для всех стратегий

### Interface Segregation Principle
- Минимальный интерфейс для стратегий
- Опциональные методы для расширенной функциональности

### Dependency Inversion Principle
- Зависимость от абстракций, а не от конкретных классов
- Использование DI контейнера для управления зависимостями

