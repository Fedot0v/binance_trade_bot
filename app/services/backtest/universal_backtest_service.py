"""
Universal backtest service for any strategies
"""
from typing import Dict, Any, List, Optional, Union
import pandas as pd
from datetime import datetime

from services.backtest.universal_backtest_engine import UniversalBacktestEngine, BacktestContext
from services.backtest.csv_data_service import CSVDataService
from services.backtest.csv_loader_service import CSVLoaderService
from services.backtest.market_data_utils import MarketDataUtils
from schemas.backtest import BacktestResult
from strategies.contracts import Strategy


class UniversalBacktestService:
    """
    Universal service for backtesting any strategies.

    This service:
    - Works with any strategy implementing the Strategy protocol.
    - Supports both single and multiple symbols.
    - Can load data from CSV files or download from exchanges.
    - Provides flexible configuration for fees, slippage, etc.
    """

    def __init__(
        self,
        csv_service: Optional[CSVDataService] = None,
        csv_loader: Optional[CSVLoaderService] = None,
        config: Dict[str, Any] = None
    ):
        self.csv_service = csv_service or CSVDataService()
        self.csv_loader = csv_loader or CSVLoaderService()

        self.default_config = {
            'fee_rate': 0.0004,
            'slippage_bps': 0.0,
            'spread_bps': 0.0,
            'intrabar_mode': 'stopfirst'
        }

        if config:
            self.default_config.update(config)

    async def run_backtest(
        self,
        strategy: Strategy,
        template: Any,
        data_source: str = 'file',
        symbols: Union[str, List[str]] = 'BTCUSDT',
        csv_files: Union[str, List[str]] = None,
        start_date: str = None,
        end_date: str = None,
        initial_balance: float = 10000.0,
        leverage: int = 1,
        config: Dict[str, Any] = None
    ) -> BacktestResult:
        """
        Runs a backtest for the strategy.

        Args:
            strategy: The strategy implementing the Strategy protocol.
            template: Strategy template with parameters.
            data_source: Data source ('file' or 'download').
            symbols: Symbol(s) to test.
            csv_files: Path(s) to CSV file(s).
            start_date: Start date (for download).
            end_date: End date (for download).
            initial_balance: Initial balance.
            config: Backtest configuration.

        Returns:
            BacktestResult: The backtest result.
        """
        print("🚀 Starting universal backtest")
        print(f"📊 Strategy: {strategy.id}")
        print(f"💰 Initial balance: ${initial_balance:,.2f}")

        if isinstance(symbols, str):
            symbols = [symbols]

        market_data = await self._load_market_data(
            data_source, symbols, csv_files, start_date, end_date, template
        )

        backtest_config = self.default_config.copy()
        if config:
            backtest_config.update(config)

        context = BacktestContext(
            strategy=strategy,
            template=template,
            initial_balance=initial_balance,
            market_data=market_data,
            config=backtest_config,
            leverage=leverage
        )

        engine = UniversalBacktestEngine(context)
        result = await engine.run()

        print("✅ Backtest completed successfully!")
        print(f"💰 Final balance: ${result.final_balance:.2f}")
        print(f"📊 Total trades: {result.total_trades}")

        if hasattr(result, 'trades') and result.trades:
            print(f"\n💰 POSITION DETAILS:")
            for i, trade in enumerate(result.trades[:3]):
                if hasattr(trade, 'get'):
                    entry_size = trade.get('entry_size_usd', trade.get('size_usd', getattr(trade, 'size', 0)))
                    leverage = trade.get('leverage', 1)
                    symbol = trade.get('symbol', 'N/A')
                    side = trade.get('side', 'N/A')
                    pnl = trade.get('pnl', 0)
                else:
                    entry_size = getattr(trade, 'size', 0)
                    leverage = getattr(trade, 'leverage', getattr(result, 'leverage', 1))
                    symbol = getattr(trade, 'symbol', 'N/A')
                    side = getattr(trade, 'side', 'N/A')
                    pnl = getattr(trade, 'pnl', 0)

                # Безопасные приведения типов и значения по умолчанию
                try:
                    entry_size = float(entry_size or 0)
                except (TypeError, ValueError):
                    entry_size = 0.0

                try:
                    leverage = int(leverage or 1)
                except (TypeError, ValueError):
                    leverage = 1

                pnl = 0.0 if pnl is None else pnl
                try:
                    pnl = float(pnl)
                except (TypeError, ValueError):
                    pnl = 0.0

                actual_position_value = entry_size * leverage if leverage > 1 else entry_size

                print(f"  {i+1}. {symbol} {side}")
                print(f"     💵 Position size: ${entry_size:.2f}")
                print(f"     ⚡ Leverage: {leverage}x")
                print(f"     🎯 Actual amount: ${actual_position_value:.2f}")
                print(f"     💰 PnL: ${pnl:+.2f}")

            if len(result.trades) > 3:
                print(f"  ... and {len(result.trades) - 3} more trades")

        return result

    async def _load_market_data(
        self,
        data_source: str,
        symbols: List[str],
        csv_files: Union[str, List[str]],
        start_date: str,
        end_date: str,
        template: Any
    ) -> Dict[str, pd.DataFrame]:
        """
        Loads market data.
        """
        market_data = {}

        if data_source == 'file':
            if isinstance(csv_files, str):
                csv_files = [csv_files]

            if not csv_files or len(csv_files) != len(symbols):
                print(f"🔍 Auto-searching CSV files for symbols: {symbols}")
                csv_files = self._find_csv_files_for_symbols(symbols)

            if not csv_files or len(csv_files) != len(symbols):
                raise ValueError(f"No CSV files found for symbols: {symbols}")

            for symbol, csv_file in zip(symbols, csv_files):
                df = self.csv_service.load_csv_data(csv_file)
                market_data[symbol] = df
                print(f"📁 Loaded data {symbol} from {csv_file}: {len(df)} candles")

            # Синхронизируем пары, если загружали несколько символов
            if len(symbols) >= 2 and 'BTCUSDT' in market_data and 'ETHUSDT' in market_data:
                market_data['BTCUSDT'], market_data['ETHUSDT'] = \
                    MarketDataUtils.synchronize_two(
                        market_data['BTCUSDT'],
                        market_data['ETHUSDT']
                    )
                print("✅ Data synchronized by time (file) for BTCUSDT/ETHUSDT")
                try:
                    print(f"   BTC last: {market_data['BTCUSDT'].index[-1]} candles={len(market_data['BTCUSDT'])}")
                    print(f"   ETH last: {market_data['ETHUSDT'].index[-1]} candles={len(market_data['ETHUSDT'])}")
                except Exception:
                    pass

        elif data_source == 'download':
            if not start_date or not end_date:
                raise ValueError("start_date and end_date are required for download")

            interval = '1m'
            if template:
                interval = getattr(template, 'interval', '1m') or '1m'

            # Если несколько символов, загружаем их по отдельности
            for symbol in symbols:
                csv_path = self.csv_loader.download_from_binance(
                    symbol, start_date, end_date, interval
                )
                try:
                    df = self.csv_service.load_csv_data(csv_path)
                    market_data[symbol] = df
                    print(f"📥 Downloaded data {symbol}: {len(df)} candles")
                finally:
                    self.csv_loader.cleanup_temp_file(csv_path)

            # Синхронизируем пары при загрузке с биржи
            if len(symbols) >= 2 and 'BTCUSDT' in market_data and 'ETHUSDT' in market_data:
                market_data['BTCUSDT'], market_data['ETHUSDT'] = \
                    MarketDataUtils.synchronize_two(
                        market_data['BTCUSDT'],
                        market_data['ETHUSDT']
                    )
                print("✅ Data synchronized by time (download) for BTCUSDT/ETHUSDT")
                try:
                    print(f"   BTC last: {market_data['BTCUSDT'].index[-1]} candles={len(market_data['BTCUSDT'])}")
                    print(f"   ETH last: {market_data['ETHUSDT'].index[-1]} candles={len(market_data['ETHUSDT'])}")
                except Exception:
                    pass

        else:
            raise ValueError("data_source must be 'file' or 'download'")

        return market_data

    def _find_csv_files_for_symbols(self, symbols: List[str]) -> List[str]:
        """
        Automatically finds CSV files for given symbols.
        """
        import os

        found_files = []
        available_files = [f for f in os.listdir('.') if f.endswith('.csv')]

        print(f"📂 Available CSV files: {available_files}")

        for symbol in symbols:
            matching_files = [f for f in available_files if f.startswith(symbol)]

            if matching_files:
                file_path = max(matching_files, key=lambda x: x)
                found_files.append(file_path)
                print(f"✅ File found for {symbol}: {file_path}")
            else:
                print(f"⚠️ No suitable files found for {symbol}")
                return []

        return found_files

    async def run_multi_symbol_backtest(
        self,
        strategy: Strategy,
        template: Any,
        symbols: List[str],
        data_source: str = 'file',
        csv_files: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        initial_balance: float = 10000.0,
        config: Dict[str, Any] = None
    ) -> BacktestResult:
        """
        Runs a backtest for multiple symbols.

        This is a convenience method for strategies working with multiple symbols.
        """
        return await self.run_backtest(
            strategy=strategy,
            template=template,
            data_source=data_source,
            symbols=symbols,
            csv_files=csv_files,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            config=config
        )

    async def run_compensation_backtest(
        self,
        strategy: Strategy,
        template: Any,
        symbols: List[str],
        data_source: str = 'file',
        csv_file1: str = None,
        csv_file2: str = None,
        start_date: str = None,
        end_date: str = None,
        initial_balance: float = 10000.0,
        config: Dict[str, Any] = None
    ) -> BacktestResult:
        """
        Runs a compensation backtest (with BTC and ETH).

        For compensation strategy, data for both symbols is required.
        """
        # symbols = [symbol1, symbol2] # Больше не нужно, symbols приходит как List[str]
        csv_files = [csv_file1, csv_file2] if csv_file1 and csv_file2 else None

        return await self.run_backtest(
            strategy=strategy,
            template=template,
            data_source=data_source,
            symbols=symbols, # Передаем symbols напрямую
            csv_files=csv_files,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            config=config
        )

    def get_available_config_options(self) -> Dict[str, Any]:
        """
        Get available configuration options.
        """
        return {
            'fee_rate': {
                'description': 'Exchange fee (taker) in fractions',
                'default': 0.0004,
                'type': 'float'
            },
            'slippage_bps': {
                'description': 'Slippage in basis points',
                'default': 0.0,
                'type': 'float'
            },
            'spread_bps': {
                'description': 'Full spread in basis points',
                'default': 0.0,
                'type': 'float'
            },
            'intrabar_mode': {
                'description': 'SL/TP processing mode in one candle',
                'default': 'stopfirst',
                'options': ['stopfirst', 'tpfirst', 'mid'],
                'type': 'str'
            }
        }

    def create_config(
        self,
        fee_rate: float = None,
        slippage_bps: float = None,
        spread_bps: float = None,
        intrabar_mode: str = None
    ) -> Dict[str, Any]:
        """
        Creates a backtest configuration.
        """
        config = {}

        if fee_rate is not None:
            config['fee_rate'] = fee_rate
        if slippage_bps is not None:
            config['slippage_bps'] = slippage_bps
        if spread_bps is not None:
            config['spread_bps'] = spread_bps
        if intrabar_mode is not None:
            config['intrabar_mode'] = intrabar_mode

        return config
