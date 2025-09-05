import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import os

from strategies.registry import REGISTRY, list_available
from services.strategy_parameters import StrategyParameters
from services.csv_data_service import CSVDataService
from services.backtest_statistics_service import BacktestStatisticsService
from services.strategy_config_service import StrategyConfigService
from schemas.backtest import BacktestResult, BacktestTrade, BacktestEquityPoint, AvailableStrategy
from schemas.user_strategy_template import UserStrategyTemplateRead
from services.backtest.position_manager import PositionManager
# SOLID helpers
from services.backtest.backtest_trade_executor import BacktestTradeExecutor
from services.backtest.market_data_utils import MarketDataUtils
from services.strategy_manager import BacktestStrategyManager
from services.csv_loader_service import CSVLoaderService
from services.backtest.data_feed import DataFeed
from services.backtest.decision_policy import (
    should_analyze_for_entry,
    should_analyze_compensation_entry,
    build_open_state,
)
# Оркестраторы бэктеста
from services.backtest.orchestrator_single import SingleBacktestOrchestrator
from services.backtest.orchestrator_dual import DualBacktestOrchestrator
# removed unused/broken imports: BacktestStrategyFactory, UniversalBacktestAdapter


class BacktestService:
    """Универсальный сервис для бектестинга шаблонов стратегий"""
    
    def __init__(self, strategy_config_service: StrategyConfigService = None, *, slippage_bps: float = 0.0, spread_bps: float = 0.0, intrabar_mode: str = 'stopfirst'):
        self.csv_service = CSVDataService()
        self.stats_service = BacktestStatisticsService()
        self.strategy_config_service = strategy_config_service
        self.available_strategies = list_available()
        # Комиссия биржи (taker) на одну сторону, по умолчанию 0.04%
        self.FEE_RATE = 0.0004
        # Управление позициями (закрытие, pnl и т.п.)
        self.position_manager = PositionManager(fee_rate=self.FEE_RATE, intrabar_mode=intrabar_mode)
        # Исполнитель сделок для бэктеста
        self.backtest_executor = BacktestTradeExecutor(fee_rate=self.FEE_RATE, slippage_bps=slippage_bps, spread_bps=spread_bps)
        # Создание и выбор стратегий (вариант для бэктеста)
        self.strategy_manager = BacktestStrategyManager()
        # Загрузка CSV из внешних источников
        self.csv_loader = CSVLoaderService()
        # Лента данных
        self.data_feed = DataFeed()
        # Инициализация оркестраторов
        self.single_orchestrator = SingleBacktestOrchestrator(
            position_manager=self.position_manager,
            backtest_executor=self.backtest_executor,
            stats_service=self.stats_service,
            data_feed=self.data_feed,
        )
        self.dual_orchestrator = DualBacktestOrchestrator(
            position_manager=self.position_manager,
            backtest_executor=self.backtest_executor,
            stats_service=self.stats_service,
            data_feed=self.data_feed,
        )
    
    def get_available_strategies(self) -> List[AvailableStrategy]:
        """Возвращает список доступных шаблонов стратегий"""
        return [AvailableStrategy(**strategy) for strategy in self.available_strategies]

    # Публичные методы запуска бектеста по CSV/скачиванию
    def _extract_parameters_safely(self, template) -> dict:
        """Безопасно извлекает параметры из шаблона, обрабатывая как dict, так и SimpleNamespace"""
        if not template or not hasattr(template, 'parameters') or not template.parameters:
            return {}

        parameters = template.parameters

        # Если это уже словарь - возвращаем как есть
        if isinstance(parameters, dict):
            return parameters

        # Если это SimpleNamespace или другой объект с __dict__
        if hasattr(parameters, '__dict__'):
            return parameters.__dict__

        # Если это итерируемый объект (но не строка)
        if hasattr(parameters, '__iter__') and not isinstance(parameters, str):
            try:
                return dict(parameters)
            except (ValueError, TypeError):
                pass

        # В остальных случаях возвращаем пустой словарь
        return {}

    async def run_novichok_csv(
        self,
        template: UserStrategyTemplateRead,
        csv_file_path: str,
        initial_balance: float = 10000.0,
        leverage: int = 1,
    ) -> BacktestResult:
        df = self.csv_service.load_csv_data(csv_file_path)
        parameters = self._extract_parameters_safely(template)
        return await self._execute_backtest_with_parameters(
            data=df,
            initial_balance=initial_balance,
            strategy_name=template.template_name,
            symbol=getattr(template, 'symbol', 'BTCUSDT') or 'BTCUSDT',
            parameters=parameters,
            template=template,
            leverage=leverage,
        )

    async def run_novichok_download(
        self,
        template: UserStrategyTemplateRead,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0,
        leverage: int = 1,
    ) -> BacktestResult:
        csv_path = self.csv_loader.download_from_binance(
            symbol, start_date, end_date, getattr(template, 'interval', '1m') or '1m'
        )
        try:
            return await self.run_novichok_csv(template, csv_path, initial_balance, leverage)
        finally:
            self.csv_loader.cleanup_temp_file(csv_path)

    async def run_compensation_csv(
        self,
        template: UserStrategyTemplateRead,
        csv_btc_path: str,
        csv_eth_path: str,
        initial_balance: float = 10000.0,
        symbol1: str = 'BTCUSDT',
        symbol2: str = 'ETHUSDT'
    ) -> BacktestResult:
        df1 = self.csv_service.load_csv_data(csv_btc_path)
        df2 = self.csv_service.load_csv_data(csv_eth_path)
        df1, df2 = MarketDataUtils.synchronize_two(df1, df2)
        parameters = template.parameters or {}
        return await self._execute_compensation_backtest(
            btc_data=df1,
            eth_data=df2,
            initial_balance=initial_balance,
            strategy_name=template.template_name,
            symbol1=symbol1,
            symbol2=symbol2,
            parameters=parameters,
            template=template,
        )

    async def run_compensation_download(
        self,
        template: UserStrategyTemplateRead,
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0,
        symbol1: str = 'BTCUSDT',
        symbol2: str = 'ETHUSDT'
    ) -> BacktestResult:
        interval = getattr(template, 'interval', '1m') or '1m'
        p1, p2 = self.csv_loader.download_dual_from_binance(symbol1, symbol2, start_date, end_date, interval)
        try:
            return await self.run_compensation_csv(template, p1, p2, initial_balance, symbol1, symbol2)
        finally:
            self.csv_loader.cleanup_temp_file(p1)
            self.csv_loader.cleanup_temp_file(p2)
    
    async def run_backtest(
        self,
        strategy_key: str,
        data_source: str,  # 'file' или 'download'
        symbol: str = "BTCUSDT",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        csv_file_path: Optional[str] = None,
        initial_balance: float = 10000.0,
        parameters: Optional[Dict[str, Any]] = None
    ) -> BacktestResult:
        """
        Запускает бектест шаблона стратегии
        
        Args:
            strategy_key: Ключ шаблона стратегии из реестра
            data_source: Источник данных ('file' или 'download')
            symbol: Торговая пара (для скачивания)
            start_date: Дата начала (YYYY-MM-DD)
            end_date: Дата окончания (YYYY-MM-DD)
            csv_file_path: Путь к CSV файлу (если data_source='file')
            initial_balance: Начальный баланс
            parameters: Параметры стратегии
        """
        
        # Проверяем доступность шаблона стратегии
        if strategy_key not in REGISTRY:
            raise ValueError(f"Шаблон стратегии '{strategy_key}' не найден в реестре")
        
        strategy_info = REGISTRY[strategy_key]
        strategy_class = strategy_info['cls']
        
        # Подготавливаем параметры
        if parameters is None:
            parameters = strategy_info.get('default_parameters', {})
        
        # Загружаем данные
        if data_source == 'download':
            if not start_date or not end_date:
                raise ValueError("Для скачивания данных нужны start_date и end_date")
            
            csv_file_path = self.csv_loader.download_from_binance(symbol, start_date, end_date)
            should_cleanup = True
        elif data_source == 'file':
            if not csv_file_path:
                raise ValueError("Для файлового источника нужен csv_file_path")
            should_cleanup = False
        else:
            raise ValueError("data_source должен быть 'file' или 'download'")
        
        try:
            # Загружаем данные
            df = self.csv_service.load_csv_data(csv_file_path)
            
            if df.empty:
                raise ValueError("Не удалось загрузить данные")
            
            # Создаем стратегию через make_strategy (которая возвращает адаптер)
            from strategies.strategy_factory import make_strategy

            # Создаем простой template объект с необходимыми полями
            class SimpleTemplate:
                def __init__(self):
                    self.template_name = strategy_key
                    self.symbol = symbol
                    self.interval = "1m"
                    self.leverage = 1
                    self.parameters = parameters or {}

            template = SimpleTemplate()
            strategy = make_strategy(strategy_key, template)

            # Запускаем бектест (унифицированный async-пайплайн)
            result = await self._execute_backtest_with_parameters(
                data=df,
                initial_balance=initial_balance,
                strategy_name=strategy_info['name'],
                symbol=symbol,
                parameters=parameters,
                template=template
            )
            
            return result
            
        finally:
            # Очищаем временный файл
            if should_cleanup and csv_file_path:
                self.csv_loader.cleanup_temp_file(csv_file_path)
    
    async def run_backtest_with_template(
        self,
        template: UserStrategyTemplateRead,
        data_source: str,  # 'file' или 'download'
        symbol: str = "BTCUSDT",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        csv_file_path: Optional[str] = None,
        initial_balance: float = 10000.0
    ) -> BacktestResult:
        """
        Запускает бектест с шаблоном стратегии пользователя
        
        Args:
            template: Шаблон стратегии пользователя
            data_source: Источник данных ('file' или 'download')
            symbol: Торговая пара (для скачивания)
            start_date: Дата начала (YYYY-MM-DD)
            end_date: Дата окончания (YYYY-MM-DD)
            csv_file_path: Путь к CSV файлу (если data_source='file')
            initial_balance: Начальный баланс
        """
        
        # Загружаем данные
        if data_source == 'download':
            if not start_date or not end_date:
                raise ValueError("Для скачивания данных нужны start_date и end_date")
            
            csv_file_path = self.csv_loader.download_from_binance(symbol, start_date, end_date)
            should_cleanup = True
        elif data_source == 'file':
            if not csv_file_path:
                raise ValueError("Для файлового источника нужен csv_file_path")
            should_cleanup = False
        else:
            raise ValueError("data_source должен быть 'file' или 'download'")
        
        try:
            # Загружаем данные
            df = self.csv_service.load_csv_data(csv_file_path)
            
            if df.empty:
                raise ValueError("Не удалось загрузить данные")
            
            # Используем параметры из шаблона пользователя
            parameters = self._extract_parameters_safely(template)

            # Логируем параметры для отладки
            print(f"🔍 Параметры стратегии для бектеста: {parameters}")
            print(f"🔍 Тип параметров: {type(parameters)}")
            if parameters:
                # Дополнительная проверка безопасности
                safe_params = parameters if isinstance(parameters, dict) else self._extract_parameters_safely(template)
                for key, value in safe_params.items():
                    print(f"🔍 {key}: {value} (тип: {type(value)})")
            
            # Запускаем бектест с параметрами шаблона
            result = await self._execute_backtest_with_parameters(
                data=df,
                initial_balance=initial_balance,
                strategy_name=template.template_name,
                symbol=symbol,
                parameters=parameters,
                template=template
            )
            
            return result
            
        finally:
            # Очищаем временный файл
            if should_cleanup and csv_file_path:
                self.csv_loader.cleanup_temp_file(csv_file_path)

    async def run_compensation_backtest_with_template(
        self,
        template: UserStrategyTemplateRead,
        symbol1: str = "BTCUSDT",
        symbol2: str = "ETHUSDT",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        csv_file_path1: Optional[str] = None,
        csv_file_path2: Optional[str] = None,
        initial_balance: float = 10000.0
    ) -> BacktestResult:
        """
        Запускает бектест компенсационной стратегии с двумя символами
        """
        print(f"\n🚀 ЗАПУСК КОМПЕНСАЦИОННОГО БЕКТЕСТА:")
        print(f"  📊 Символ 1: {symbol1}")
        print(f"  📊 Символ 2: {symbol2}")
        print(f"  📅 Начальная дата: {start_date}")
        print(f"  📅 Конечная дата: {end_date}")
        print(f"  💰 Начальный баланс: ${initial_balance:,.2f}")
        print(f"  🔧 Шаблон: {template.template_name}")
        print(f"  📁 CSV файл 1: {csv_file_path1}")
        print(f"  📁 CSV файл 2: {csv_file_path2}")
        
        try:
            # Загружаем данные для двух символов
            if csv_file_path1 and csv_file_path2:
                print(f"📁 Загружаем данные из CSV файлов...")
                df1 = self.csv_service.load_csv_data(csv_file_path1)
                df2 = self.csv_service.load_csv_data(csv_file_path2)
                print(f"✅ CSV данные загружены: BTC {len(df1)} свечей, ETH {len(df2)} свечей")
            else:
                print(f"📥 Скачиваем данные с Binance...")
                # Скачиваем данные с Binance
                interval = template.interval or "1m"
                print(f"  ⏰ Интервал: {interval}")
                csv_file_path1, csv_file_path2 = self.csv_loader.download_dual_from_binance(
                    symbol1, symbol2, start_date, end_date, interval
                )
                print(f"  📁 Скачаны файлы: {csv_file_path1}, {csv_file_path2}")
                
                df1 = self.csv_service.load_csv_data(csv_file_path1)
                df2 = self.csv_service.load_csv_data(csv_file_path2)
                print(f"✅ Данные скачаны и загружены: BTC {len(df1)} свечей, ETH {len(df2)} свечей")
                
                # Очищаем временные файлы
                self.csv_loader.cleanup_temp_file(csv_file_path1)
                self.csv_loader.cleanup_temp_file(csv_file_path2)
                print(f"🧹 Временные файлы очищены")

            print(f"📊 Синхронизируем данные по времени...")
            # Синхронизируем данные по времени
            df1, df2 = MarketDataUtils.synchronize_two(df1, df2)
            print(f"✅ Данные синхронизированы: BTC {len(df1)} свечей, ETH {len(df2)} свечей")

            # Извлекаем параметры из шаблона
            parameters = self._extract_parameters_safely(template)

            # Логируем параметры для отладки
            print(f"🔍 Параметры компенсационной стратегии для бектеста: {parameters}")
            print(f"🔍 Тип параметров: {type(parameters)}")
            if parameters:
                # Дополнительная проверка безопасности
                safe_params = parameters if isinstance(parameters, dict) else self._extract_parameters_safely(template)
                for key, value in safe_params.items():
                    print(f"🔍 {key}: {value} (тип: {type(value)})")
            
            print(f"🎯 Запускаем _execute_compensation_backtest...")
            # Запускаем компенсационный бектест, учитывая обе выборки BTC и ETH
            result = await self._execute_compensation_backtest(
                btc_data=df1,
                eth_data=df2,
                initial_balance=initial_balance,
                strategy_name=template.template_name,
                symbol1=symbol1,
                symbol2=symbol2,
                parameters=parameters,
                template=template
            )
            
            print(f"✅ Компенсационный бектест завершен успешно!")
            return result
            
        except Exception as e:
            print(f"❌ ОШИБКА в run_compensation_backtest_with_template: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    # Удалена синхронная версия исполнения; используем только async-пайплайн
    
    async def _execute_backtest_with_parameters(
        self,
        data: pd.DataFrame,
        initial_balance: float,
        strategy_name: str,
        symbol: str,
        parameters: Dict[str, Any],
        template: UserStrategyTemplateRead,
        leverage: int = 1
    ) -> BacktestResult:
        """Выполняет бектест с параметрами шаблона стратегии пользователя (использует новую архитектуру)"""

        # Получаем конфигурацию стратегии по ID, как в реальной торговле
        strategy_config = await self.strategy_config_service.get_by_id(template.strategy_config_id)
        if not strategy_config:
            raise ValueError(f"Не найдена конфигурация стратегии с ID {template.strategy_config_id}")

        # Убеждаемся что параметры в правильном формате
        if not isinstance(parameters, dict):
            parameters = self._extract_parameters_safely(template)

        print(f"🔍 АНАЛИЗ ОПРЕДЕЛЕНИЯ СТРАТЕГИИ:")
        print(f"  📋 Название шаблона: {template.template_name}")
        print(f"  ⚙️ Параметры шаблона: {parameters}")
        print(f"  🔧 Конфигурация стратегии: {strategy_config.name}")
        strategy_key = self.strategy_manager.determine_strategy_key(template, parameters, strategy_config.name)

        print(f"  🎯 Определена стратегия: {strategy_key}")

        # Создаем стратегию через фабрику
        strategy = self.strategy_manager.make_strategy(strategy_key, template)
        if not strategy:
            raise ValueError(f"Не удалось создать стратегию {strategy_key}")

        print(f"✅ Стратегия создана: {strategy.__class__.__name__}")

        # Для compensation используем dual orchestrator с автоматической загрузкой ETH данных
        if strategy_key == "compensation":
            print(f"🎯 Используем dual orchestrator для compensation стратегии")
            # Загружаем ETH данные для компенсационной стратегии
            eth_data = await self._get_eth_data_for_compensation(template)
            if eth_data is None or eth_data.empty:
                print("⚠️ Не удалось получить данные ETH для компенсации, используем single orchestrator")
                # Fallback на single orchestrator без ETH данных
                return await self.single_orchestrator.execute(
                    data=data,
                    initial_balance=initial_balance,
                    strategy=strategy,
                    strategy_name=strategy_name,
                    symbol=symbol,
                    parameters=parameters,
                    template=template,
                    leverage=leverage,
                )
            else:
                print(f"✅ Данные ETH загружены: {len(eth_data)} свечей")
                btc_data, eth_data = MarketDataUtils.synchronize_pair(data, eth_data)
                return await self.dual_orchestrator.execute(
                    btc_data=btc_data,
                    eth_data=eth_data,
                    initial_balance=initial_balance,
                    strategy=strategy,
                    strategy_name=strategy_name,
                    symbol1=symbol,
                    symbol2="ETHUSDT",
                    parameters=parameters,
                    template=template,
                )
        # Иначе используем single orchestrator
        return await self.single_orchestrator.execute(
            data=data,
            initial_balance=initial_balance,
            strategy=strategy,
            strategy_name=strategy_name,
            symbol=symbol,
            parameters=parameters,
            template=template,
            leverage=leverage,
        )

    # Удалено: вынесено в decision_policy.should_analyze_for_entry

    # Удалено: вынесено в decision_policy.should_analyze_compensation_entry

    # Удалено: логика открытия позиции перенесена в TradeSimulator.can_open_position

    def _create_open_state_for_strategy(self, open_positions: Dict) -> Dict:
        """
        Создает состояние для стратегии (имитирует реальную торговлю)
        """
        # В реальной торговле стратегия получает информацию об открытых позициях
        open_state = {}
        
        for symbol, position in open_positions.items():
            open_state[symbol] = {
                'deal_id': position['deal_id'],
                'entry_price': position['entry_price'],
                'entry_time': position['entry_time'],
                'side': position['side'],
                'position': position
            }
        
        return open_state

    async def _check_and_close_positions(
        self, open_positions: Dict, md: Dict, current_time, balance: float, trades: List, strategy=None
    ) -> float:
        """
        Делегирует проверку и закрытие позиций менеджеру позиций.
        """
        return await self.position_manager.check_and_close_positions_async(
            open_positions=open_positions,
            market_data=md,
            current_time=current_time,
            balance=balance,
            trades=trades,
            strategy=strategy,
        )

    def _check_position_close_conditions(self, position: Dict, current_price: float, current_time) -> Tuple[bool, str]:
        """
        Делегирует проверку условий закрытия менеджеру позиций.
        Поддержка совместимости: формируем OHLC из одной цены.
        """
        ohlc = {'open': current_price, 'high': current_price, 'low': current_price, 'close': current_price}
        should_close, reason, _ = self.position_manager.check_close_conditions(position, ohlc, current_time)
        return should_close, reason

    def _check_and_close_positions_sync(
        self, open_positions: Dict, md: Dict, current_time, balance: float, trades: List, strategy=None
    ) -> float:
        """
        Делегирует синхронную проверку и закрытие позиций менеджеру позиций.
        """
        return self.position_manager.check_and_close_positions_sync(
            open_positions=open_positions,
            market_data=md,
            current_time=current_time,
            balance=balance,
            trades=trades,
            strategy=strategy,
        )

    def _calculate_pnl(self, position: Dict, current_price: float) -> float:
        """
        Делегирует расчет PnL менеджеру позиций.
        """
        return self.position_manager.calculate_pnl(position, current_price)

    def _calculate_pnl_pct(self, position: Dict, current_price: float) -> float:
        """Возвращает относительный PnL (делегируется менеджеру позиций)."""
        return self.position_manager.calculate_pnl_pct(position, current_price)

    def _calculate_position_size_from_parameters(self, balance: float, parameters: Dict[str, Any], template: UserStrategyTemplateRead) -> float:
        """Рассчитывает размер позиции на основе параметров шаблона"""
        try:
            leverage = float(template.leverage)
        except (ValueError, TypeError):
            leverage = 1.0
            
        # Безопасно извлекаем deposit_prct
        try:
            deposit_prct_raw = parameters.get('deposit_prct', 0.1)
            if isinstance(deposit_prct_raw, str):
                deposit_prct = float(deposit_prct_raw)
            else:
                deposit_prct = float(deposit_prct_raw)
        except (ValueError, TypeError):
            deposit_prct = 0.1
        
        return balance * deposit_prct * leverage

    # Удалено: синхронизация перенесена в MarketDataUtils.synchronize_two

    # Удалено: исполнение сделки перенесено в TradeSimulator.simulate_trade

    async def _execute_compensation_backtest(
        self,
        btc_data: pd.DataFrame,
        eth_data: pd.DataFrame,
        initial_balance: float,
        strategy_name: str,
        symbol1: str,
        symbol2: str,
        parameters: Dict[str, Any],
        template: UserStrategyTemplateRead
    ) -> BacktestResult:
        """
        Выполняет бектест компенсационной стратегии с двумя символами
        """
        
        # Делегируем dual orchestrator для совместимости со старым вызовом
        btc_data, eth_data = MarketDataUtils.synchronize_pair(btc_data, eth_data)
        from strategies.strategy_factory import make_strategy
        strategy = make_strategy("compensation", template)
        return await self.dual_orchestrator.execute(
            btc_data=btc_data,
            eth_data=eth_data,
            initial_balance=initial_balance,
            strategy=strategy,
            strategy_name=strategy_name,
            symbol1=symbol1,
            symbol2=symbol2,
            parameters=parameters,
            template=template,
        )

    async def _execute_backtest_with_adapter(
        self,
        strategy,
        data: pd.DataFrame,
        initial_balance: float,
        strategy_name: str,
        symbol: str,
        parameters: Dict[str, Any],
        template: UserStrategyTemplateRead
    ) -> BacktestResult:
        """Выполняет бектест через адаптер стратегии"""
        
        print(f"\n🚀 ЗАПУСК БЕКТЕСТА ЧЕРЕЗ АДАПТЕР: {strategy_name}")
        print(f"📊 Символ: {symbol}")
        print(f"💰 Начальный баланс: ${initial_balance:,.2f}")
        print(f"📅 Период: {data.index[0]} - {data.index[-1]}")
        print(f"📈 Количество свечей: {len(data)}")
        print(f"⚙️ Параметры: {parameters}")
        print(f"🔧 Шаблон: {template.template_name} (плечо: {template.leverage}x)")
        print(f"🔧 Адаптер: {strategy.__class__.__name__}")
        
        balance = initial_balance
        equity_curve = [BacktestEquityPoint(timestamp=data.index[0], balance=balance)]
        trades = []
        
        # Состояние стратегии (позиции, таймеры и т.д.)
        open_state = {}
        
        print(f"\n📋 Начинаем проход по свечам...")
        
        # Проходим по всем свечам, начинаем с первой для полного анализа
        for i in range(len(data)):
            current_time = data.index[i]
            # Для первых свечей используем доступные данные, для остальных - все исторические
            if i < 50:  # Для первых 50 свечей используем только доступные
                current_data = data.iloc[:i+1]
            else:  # Для остальных используем все исторические данные
                current_data = data.iloc[:i+1]
            
            # Проверяем, что у нас есть данные на текущей свече
            if i >= len(data):
                print(f"⚠️ Нет данных для свечи {i}, пропускаем")
                continue
            current_price = current_data['close'].iloc[-1]
            
            # Логируем каждые 100 свечей для отслеживания прогресса
            if i % 100 == 0:
                print(f"⏰ Время: {current_time}, Свеча: {i}/{len(data)}, Баланс: ${balance:,.2f}")
                print(f"  🔍 Состояние стратегии: {open_state}")
            
            # Вызываем стратегию через адаптер - она сама решает что делать
            if hasattr(strategy, 'decide'):
                md = {symbol: current_data}
                decision = await strategy.decide(md, template, open_state)
                print(f"🎯 Решение стратегии: {decision}")
                
                # Обрабатываем решения стратегии
                if decision and not decision.is_empty():
                    for intent in decision.intents:
                        if intent.symbol == symbol:
                            # Выполняем торговую операцию через симулятор
                            trade_result = self.trade_simulator.simulate_trade(
                                intent=intent,
                                current_price=current_price,
                                current_time=current_time,
                                balance=balance,
                                symbol=symbol
                            )
                            if trade_result:
                                trades.append(trade_result)
                                balance = trade_result['new_balance']
                                print(f"💰 Выполнена сделка: {intent.side} {intent.symbol} по цене ${current_price:.2f}")
                                print(f"  💰 Новый баланс: ${balance:.2f}")
            else:
                signal = strategy.generate_signal(current_data)
                print(f"🎯 Сигнал стратегии: {signal}")
            
            # Обновляем кривую доходности
            equity_curve.append(BacktestEquityPoint(
                timestamp=current_time,
                balance=balance
            ))
        
        print(f"\n🏁 ЗАВЕРШЕНИЕ БЕКТЕСТА:")
        print(f"  📊 Всего свечей обработано: {len(data)}")
        print(f"  💰 Финальный баланс: ${balance:,.2f}")
        print(f"  📈 Общая доходность: {((balance/initial_balance)-1)*100:+.2f}%")
        print(f"  🔢 Количество сделок: {len(trades)}")
        
        # Рассчитываем статистику
        stats = self.stats_service.calculate_statistics(trades, equity_curve, initial_balance)
        
        print(f"\n📊 СТАТИСТИКА БЕКТЕСТА:")
        print(f"  🎯 Win Rate: {stats.get('win_rate', 0):.1f}%")
        print(f"  💰 Profit Factor: {stats.get('profit_factor', 0):.2f}")
        print(f"  📉 Максимальная просадка: {stats.get('max_drawdown', 0)*100:.2f}%")
        print(f"  📈 Коэффициент Шарпа: {stats.get('sharpe_ratio', 0):.2f}")
        
        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=data.index[0],
            end_date=data.index[-1],
            initial_balance=initial_balance,
            final_balance=balance,
            total_trades=len(trades),
            trades=trades,
            equity_curve=equity_curve,
            parameters=parameters,
            **stats
        )

    async def _get_eth_data_for_compensation(self, template) -> Optional[pd.DataFrame]:
        """
        Получает данные ETH для компенсационной стратегии
        Автоматически определяет правильный файл на основе периода BTC данных
        """
        try:
            # Список всех возможных файлов (сначала проверяем самые свежие)
            file_periods = [
                "last-2-months",
                "april-august-2025",
                "july-august-2024",
                "last-week",
                "two-weeks-ago",
                "2025-05"
            ]

            # Ищем существующий файл BTC для определения периода
            btc_file_path = None
            for period in file_periods:
                btc_file = f"BTCUSDT-1m-{period}.csv"
                if os.path.exists(btc_file):
                    btc_file_path = btc_file
                    print(f"✅ Найден BTC файл: {btc_file_path}")
                    break

            if not btc_file_path:
                print(f"⚠️ Не найден файл BTC данных для определения периода")
                print(f"   Доступные файлы в директории:")
                for file in os.listdir('.'):
                    if file.startswith('BTCUSDT') and file.endswith('.csv'):
                        print(f"   - {file}")
                return None

            # Определяем соответствующий файл ETH
            eth_file_path = btc_file_path.replace("BTCUSDT", "ETHUSDT")

            if not os.path.exists(eth_file_path):
                print(f"⚠️ Файл ETH данных не найден: {eth_file_path}")
                print(f"   Ищем альтернативные ETH файлы...")
                # Ищем любой доступный ETH файл
                for file in os.listdir('.'):
                    if file.startswith('ETHUSDT') and file.endswith('.csv'):
                        eth_file_path = file
                        print(f"   ✅ Найден альтернативный ETH файл: {eth_file_path}")
                        break
                else:
                    print(f"   ❌ ETH файлы не найдены вообще")
                    return None

            # Загружаем данные ETH
            eth_data = pd.read_csv(eth_file_path)
            eth_data['timestamp'] = pd.to_datetime(eth_data['timestamp'])
            eth_data.set_index('timestamp', inplace=True)

            print(f"📊 Загружены данные ETH: {len(eth_data)} свечей из файла {eth_file_path}")
            return eth_data

        except Exception as e:
            print(f"❌ Ошибка при загрузке данных ETH: {e}")
            import traceback
            traceback.print_exc()
            return None

    # Удалено: синхронизация пар перенесена в MarketDataUtils.synchronize_pair
