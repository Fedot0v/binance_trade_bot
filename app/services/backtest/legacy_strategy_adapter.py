"""
Адаптер для интеграции существующих стратегий с универсальным бэктестом
"""
from typing import Dict, Any, List, Union
import pandas as pd

from strategies.contracts import Strategy, Decision, OrderIntent
from strategies.strategy_factory import make_strategy


class LegacyStrategyAdapter(Strategy):
    """
    Адаптер для использования существующих стратегий в универсальном бэктесте

    Этот адаптер оборачивает существующие стратегии и адаптеры (NovichokAdapter, CompensationAdapter)
    в интерфейс Strategy, который понимает универсальный бэктест.
    """

    def __init__(self, strategy_name: str, template):
        """
        Инициализация адаптера

        Args:
            strategy_name: Имя стратегии ('novichok' или 'compensation')
            template: Шаблон стратегии с параметрами
        """
        self.strategy_name = strategy_name.lower()
        self.template = template

        # Создаем существующую стратегию через фабрику
        self.legacy_strategy = make_strategy(strategy_name, template)

        # Устанавливаем ID для универсального бэктеста
        self.id = f"legacy-{strategy_name}"

    def required_symbols(self, template=None) -> List[str]:
        """Возвращает список необходимых символов"""
        if hasattr(self.legacy_strategy, 'required_symbols'):
            return self.legacy_strategy.required_symbols(self.template)
        else:
            # Fallback для старых стратегий без required_symbols
            if self.strategy_name == 'novichok':
                symbol = getattr(self.template, 'symbol', 'BTCUSDT')
                return [symbol] if isinstance(symbol, str) else [str(symbol)]
            elif self.strategy_name == 'compensation':
                return ['BTCUSDT', 'ETHUSDT']
            else:
                return ['BTCUSDT']

    async def decide(
        self,
        md: Dict[str, pd.DataFrame],
        template=None,
        open_state: Dict[str, Any] = None
    ) -> Decision:
        """
        Принимает решение на основе рыночных данных

        Использует существующую логику стратегии
        """
        try:
            # Используем существующую стратегию
            if hasattr(self.legacy_strategy, 'decide'):
                # Новые адаптеры (NovichokAdapter, CompensationAdapter)
                return await self.legacy_strategy.decide(md, self.template, open_state)
            else:
                # Fallback для очень старых стратегий
                return await self._fallback_decide(md, open_state)

        except Exception as e:
            print(f"❌ Ошибка в LegacyStrategyAdapter.decide: {e}")
            return Decision(intents=[])

    async def _fallback_decide(
        self,
        md: Dict[str, pd.DataFrame],
        open_state: Dict[str, Any]
    ) -> Decision:
        """
        Fallback логика для старых стратегий без decide метода
        """
        if self.strategy_name == 'novichok':
            return await self._novichok_fallback(md, open_state)
        elif self.strategy_name == 'compensation':
            return await self._compensation_fallback(md, open_state)
        else:
            return Decision(intents=[])

    async def _novichok_fallback(
        self,
        md: Dict[str, pd.DataFrame],
        open_state: Dict[str, Any]
    ) -> Decision:
        """Fallback для новичка стратегии"""
        symbol = self.required_symbols()[0]
        df = md.get(symbol)

        if df is None or df.empty:
            return Decision(intents=[])

        # Используем базовую стратегию
        signal = self.legacy_strategy.generate_signal(df)

        if signal in (None, 'hold'):
            return Decision(intents=[])

        side = "BUY" if signal == "long" else "SELL"

        # Проверяем открытые позиции
        if open_state and symbol in open_state:
            pos = open_state[symbol].get('position')
            if pos:
                pos_side = pos.get('side')
                # Закрываем если сигнал противоположный
                if (pos_side == 'BUY' and side == 'SELL') or (pos_side == 'SELL' and side == 'BUY'):
                    close_intent = OrderIntent(
                        symbol=symbol,
                        side='SELL' if pos_side == 'BUY' else 'BUY',
                        sizing='close',
                        size=0,
                        role='close'
                    )
                    return Decision(intents=[close_intent])
            return Decision(intents=[])

        # Открываем позицию
        risk_pct = float(getattr(self.template, 'deposit_prct', 0.1) or 0.1)

        intent = OrderIntent(
            symbol=symbol,
            side=side,
            sizing="risk_pct",
            size=risk_pct,
            role="primary"
        )

        return Decision(intents=[intent])

    async def _compensation_fallback(
        self,
        md: Dict[str, pd.DataFrame],
        open_state: Dict[str, Any]
    ) -> Decision:
        """Fallback для компенсационной стратегии"""
        # Используем CompensationAdapter вместо собственной логики
        from strategies.compensation_adapter import CompensationAdapter

        # Создаем адаптер с правильной компенсационной стратегией
        if hasattr(self, '_compensation_adapter'):
            adapter = self._compensation_adapter
        else:
            # Создаем адаптер для бэктеста (deal_service = None)
            adapter = CompensationAdapter(self.legacy_strategy, None)
            self._compensation_adapter = adapter

        # Используем адаптер для принятия решения
        return await adapter.decide(md, self.template, open_state)

    def _should_compensate(self, btc_df: pd.DataFrame, current_price: float) -> bool:
        """Проверяет необходимость компенсации (упрощенная версия)"""
        if len(btc_df) < 10:
            return False

        # Простая проверка: цена ушла против позиции более чем на 0.5%
        entry_price = btc_df['close'].iloc[0]  # Упрощение
        price_change_pct = abs(current_price - entry_price) / entry_price

        return price_change_pct > 0.005


class LegacyBacktestService:
    """
    Сервис для запуска бэктестов с существующими стратегиями

    Использует LegacyStrategyAdapter для интеграции старых стратегий
    с универсальным бэктестом.
    """

    def __init__(self):
        from services.backtest.universal_backtest_service import UniversalBacktestService
        self.universal_service = UniversalBacktestService()

    async def run_novichok_backtest(
        self,
        template,
        data_source: str = 'file',
        csv_file_path: str = None,
        start_date: str = None,
        end_date: str = None,
        initial_balance: float = 10000.0,
        leverage: int = 1,
        config: Dict[str, Any] = None,
        symbols: Union[str, List[str]] = 'BTCUSDT' # Добавляем параметр symbols
    ):
        """
        Запуск бэктеста новичка стратегии
        """
        print("🎯 Запуск бэктеста новичка через LegacyStrategyAdapter")

        # Создаем адаптер
        strategy = LegacyStrategyAdapter('novichok', template)

        # Определяем символ
        # Здесь используем переданный symbols, а не из шаблона
        # symbol = getattr(template, 'symbol', 'BTCUSDT')
        # if hasattr(symbol, 'value'):
        #     symbol = symbol.value

        # Запускаем через универсальный сервис
        return await self.universal_service.run_backtest(
            strategy=strategy,
            template=template,
            data_source=data_source,
            symbols=symbols, # Передаем symbols
            csv_files=csv_file_path,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            leverage=leverage,
            config=config
        )

    async def run_compensation_backtest(
        self,
        template,
        data_source: str = 'file',
        csv_btc_path: str = None,
        csv_eth_path: str = None,
        start_date: str = None,
        end_date: str = None,
        initial_balance: float = 10000.0,
        config: Dict[str, Any] = None,
        symbols: List[str] = None # Добавляем параметр symbols
    ):
        """
        Запуск бэктеста компенсационной стратегии
        """
        print("🎯 Запуск бэктеста компенсации через LegacyStrategyAdapter")

        # Создаем адаптер
        strategy = LegacyStrategyAdapter('compensation', template)

        # Определяем символы. Используем переданный symbols, если есть
        # symbols_for_compensation = symbols if symbols else ['BTCUSDT', 'ETHUSDT']
        if symbols is None:
            symbols = ['BTCUSDT', 'ETHUSDT']

        # Запускаем через универсальный сервис
        return await self.universal_service.run_compensation_backtest(
            strategy=strategy,
            template=template,
            symbols=symbols, # Передаем symbols напрямую
            data_source=data_source,
            csv_file1=csv_btc_path,
            csv_file2=csv_eth_path,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            config=config
        )
