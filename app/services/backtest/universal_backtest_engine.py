"""
Universal backtest engine for any strategies
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Protocol
import pandas as pd
from datetime import datetime, timedelta

from schemas.backtest import BacktestResult, BacktestEquityPoint, BacktestTrade
from strategies.contracts import Strategy, MarketData, OpenState, Decision, OrderIntent
from strategies.compensation_strategy import CompensationStrategy


class BacktestContext:
    """Backtest execution context"""

    def __init__(
        self,
        strategy: Strategy,
        template: Any,
        initial_balance: float,
        market_data: MarketData,
        config: Dict[str, Any] = None,
        leverage: int = 1
    ):
        self.strategy = strategy
        self.template = template
        self.initial_balance = initial_balance
        self.market_data = market_data
        self.config = config or {}
        self.leverage = leverage

        # Backtest state
        self.current_balance = initial_balance
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[BacktestEquityPoint] = []
        self.current_time = None

        # Commission and risk configuration
        self.fee_rate = self.config.get('fee_rate', 0.0004)  # 0.04%
        self.slippage_bps = self.config.get('slippage_bps', 0.0)
        self.spread_bps = self.config.get('spread_bps', 0.0)
        self.intrabar_mode = self.config.get('intrabar_mode', 'stopfirst')


class BacktestEngine(ABC):
    """Abstract base class for backtest engines"""

    def __init__(self, context: BacktestContext):
        self.context = context

    @abstractmethod
    async def run(self) -> BacktestResult:
        """Run backtest and return result"""
        pass

    @abstractmethod
    def validate_context(self) -> bool:
        """Validate context before running"""
        pass

    @abstractmethod
    def get_required_symbols(self) -> List[str]:
        """Get list of required symbols for the strategy"""
        pass


class UniversalBacktestEngine(BacktestEngine):
    """Universal backtest engine"""

    def __init__(self, context: BacktestContext):
        super().__init__(context)
        self.executor = None  # Will be set later

    def validate_context(self) -> bool:
        """Validate context"""
        if not self.context.strategy:
            raise ValueError("Strategy not defined")

        if not self.context.market_data:
            raise ValueError("Market data not loaded")

        required_symbols = self.get_required_symbols()
        for symbol in required_symbols:
            if symbol not in self.context.market_data:
                raise ValueError(f"Missing data for symbol {symbol}")

        return True

    def get_required_symbols(self) -> List[str]:
        """Get required symbols"""
        return self.context.strategy.required_symbols(self.context.template)

    async def run(self) -> BacktestResult:
        """Main backtest loop"""
        self.validate_context()

        print("🚀 Starting universal backtest")
        print(f"📊 Strategy: {self.context.strategy.id}")
        print(f"💰 Initial balance: ${self.context.initial_balance:,.2f}")
        print(f"📈 Data: {list(self.context.market_data.keys())}")

        self._initialize_backtest()

        await self._run_main_loop()

        self._finalize_backtest()

        return self._build_result()

    def _initialize_backtest(self):
        """Initialize backtest"""
        all_times = []
        for df in self.context.market_data.values():
            if not df.empty:
                all_times.extend(df.index.tolist())

        if not all_times:
            raise ValueError("No data for backtest")

        unique_times = sorted(list(set(all_times)))
        self.timeline = unique_times

        if self.timeline:
            self.context.equity_curve.append(
                BacktestEquityPoint(
                    timestamp=self.timeline[0],
                    balance=self.context.initial_balance
                )
            )

    async def _run_main_loop(self):
        """Основной цикл обработки данных"""
        total_steps = len(self.timeline)

        for i, current_time in enumerate(self.timeline):
            self.context.current_time = current_time

            # Изменено: получаем текущие данные напрямую из контекста
            current_md = {symbol: df[df.index <= current_time] for symbol, df in self.context.market_data.items()}

            open_state = self._build_open_state()

            decision = await self.context.strategy.decide(current_md, self.context.template, open_state)

            if decision and not decision.is_empty():
                await self._execute_decision(decision, current_md, current_time)

            await self._update_trailing_stops(current_md, current_time)

            await self._check_and_close_positions(current_md, current_time)

            self._update_equity_curve(current_time)

    def _finalize_backtest(self):
        """Финализация бэктеста - закрытие оставшихся позиций"""
        if self.context.open_positions:
            print(f"\n🔚 Closing remaining positions: {len(self.context.open_positions)}")

            last_prices = {}
            for symbol, df in self.context.market_data.items():
                if not df.empty:
                    last_prices[symbol] = df['close'].iloc[-1]

            for symbol, position in list(self.context.open_positions.items()):
                exit_price = last_prices.get(symbol, position['entry_price'])
                self._close_position(symbol, position, exit_price, self.context.current_time, "end_of_data")

    def _build_open_state(self) -> OpenState:
        """Создать состояние открытых позиций для стратегии"""
        open_state = {}

        for symbol, position in self.context.open_positions.items():
            open_state[symbol] = {
                'deal_id': position['deal_id'],
                'entry_price': position['entry_price'],
                'entry_time': position['entry_time'],
                'side': position['side'],
                'position': position
            }

        return open_state

    async def _execute_decision(self, decision: Decision, market_data: MarketData, current_time):
        """Исполнить решение стратегии"""
        for intent in decision.intents:
            if intent.symbol not in market_data:
                print(f"⚠️ No data for symbol {intent.symbol}, skipping")
                continue

            df = market_data[intent.symbol]
            if df.empty:
                print(f"⚠️ Empty data for {intent.symbol}, skipping")
                continue

            current_price = df['close'].iloc[-1]

            await self._execute_intent(intent, current_price, current_time)

    async def _execute_intent(self, intent: OrderIntent, current_price: float, current_time):
        """Исполнить торговый intent"""
        symbol = intent.symbol

        # Check if we can open a position
        if intent.sizing == 'close':
            # Closing position
            if symbol in self.context.open_positions:
                position = self.context.open_positions[symbol]
                self._close_position(symbol, position, current_price, current_time, "strategy_signal")
        else:
            # Opening position
            if symbol in self.context.open_positions:
                print(f"⚠️ Position {symbol} already open, skipping open")
                return

            if self._can_open_position(intent, current_price):
                self._open_position(intent, current_price, current_time)

    def _can_open_position(self, intent: OrderIntent, current_price: float) -> bool:
        """Проверить, можем ли открыть позицию"""
        # Calculate position size
        if intent.sizing == "risk_pct":
            size_usd = self.context.current_balance * intent.size
        elif intent.sizing == "usd":
            size_usd = intent.size
        else:
            size_usd = self.context.current_balance * 0.01

        # Checks
        if size_usd > self.context.current_balance:
            print(f"⚠️ Insufficient funds for trade: need ${size_usd:.2f}, available ${self.context.current_balance:.2f}")
            return False

        if size_usd < 5:
            print(f"⚠️ Too small position: ${size_usd:.2f}")
            return False

        return True

    def _open_position(self, intent: OrderIntent, current_price: float, current_time):
        """Открыть позицию"""
        if intent.sizing == "risk_pct":
            size_usd = self.context.current_balance * intent.size
        elif intent.sizing == "usd":
            size_usd = intent.size
        else:
            size_usd = self.context.current_balance * 0.01

        # Apply slippage and spread
        effective_price = self._apply_price_impacts(intent.side, current_price)

        # Calculate quantity
        quantity = size_usd / effective_price

        # Open fee
        open_fee = size_usd * self.context.fee_rate

        # Update balance
        self.context.current_balance -= open_fee

        # Create position
        position = {
            'deal_id': len(self.context.trades),
            'entry_price': effective_price,
            'entry_time': current_time,
            'side': intent.side,
            'size': quantity,
            'size_usd': size_usd,
            'symbol': intent.symbol,
            'leverage': getattr(self.context.template, 'leverage', 1),
            'open_fee': open_fee,
            'stop_loss': None,  # May be set by strategy later
            'take_profit': None
        }

        self.context.open_positions[intent.symbol] = position

        # Set stop loss via strategy
        self._set_initial_stop_loss(position, intent.symbol)

        # Add trade
        trade = {
            'symbol': intent.symbol,
            'side': intent.side,
            'entry_price': effective_price,
            'entry_time': current_time,
            'size': quantity,
            'size_usd': size_usd,
            'leverage': self.context.leverage,
            'fee_open': open_fee,
            'status': 'opened'
        }

        self.context.trades.append(trade)

        print(f"💰 OPENED position: {intent.side} {quantity:.6f} {intent.symbol} @ ${effective_price:.2f}")

    def _apply_price_impacts(self, side: str, reference_price: float) -> float:
        """Применить проскальзывание и спред"""
        half_spread = self.context.spread_bps / 2 / 100  # in percentage
        slippage = self.context.slippage_bps / 100  # in percentage

        impact = half_spread + slippage

        if side == 'BUY':
            return reference_price * (1.0 + impact)
        else:
            return reference_price * (1.0 - impact)

    async def _check_and_close_positions(self, market_data: MarketData, current_time):
        """Проверить и закрыть позиции по условиям"""
        positions_to_close = []

        for symbol, position in self.context.open_positions.items():
            if symbol not in market_data:
                continue

            df = market_data[symbol]
            if df.empty:
                continue

            # Get OHLC of current candle
            last_row = df.iloc[-1]
            ohlc = {
                'open': float(last_row['open']),
                'high': float(last_row['high']),
                'low': float(last_row['low']),
                'close': float(last_row['close'])
            }

            # Check closing conditions
            should_close, reason, exit_price = self._check_close_conditions(position, ohlc, current_time)

            if should_close:
                positions_to_close.append((symbol, position, reason, exit_price))

        # Close positions
        for symbol, position, reason, exit_price in positions_to_close:
            self._close_position(symbol, position, exit_price, current_time, reason)

    def _check_close_conditions(self, position: Dict, ohlc: Dict, current_time) -> tuple[bool, str, float]:
        """Проверить условия закрытия позиции"""
        sl_price = position.get('stop_loss')
        tp_price = position.get('take_profit')

        if sl_price is not None or tp_price is not None:
            sl_hit = False
            tp_hit = False

            if sl_price is not None:
                if position['side'] == 'BUY':
                    sl_hit = ohlc['low'] <= sl_price
                else:
                    sl_hit = ohlc['high'] >= sl_price

            if tp_price is not None:
                if position['side'] == 'BUY':
                    tp_hit = ohlc['high'] >= tp_price
                else:
                    tp_hit = ohlc['low'] <= tp_price

            if sl_hit and tp_hit:
                if self.context.intrabar_mode == 'tpfirst':
                    return True, 'take_profit', tp_price
                elif self.context.intrabar_mode == 'mid':
                    # Choose the nearest target
                    open_price = ohlc['open']
                    sl_dist = abs(sl_price - open_price)
                    tp_dist = abs(tp_price - open_price)
                    if sl_dist < tp_dist:
                        return True, 'stop_loss', sl_price
                    else:
                        return True, 'take_profit', tp_price
                else:  # stopfirst
                    return True, 'stop_loss', sl_price
            elif sl_hit:
                return True, 'stop_loss', sl_price
            elif tp_hit:
                return True, 'take_profit', tp_price

        return False, '', ohlc['close']

    def _set_initial_stop_loss(self, position: Dict, symbol: str):
        """Устанавливает начальный стоп-лосс для позиции через стратегию"""
        try:
            # Создаем mock market data для стратегии
            # Используем entry_price как текущую цену для расчета стоп-лосса
            mock_df = pd.DataFrame({
                'open': [position['entry_price']],
                'high': [position['entry_price']],
                'low': [position['entry_price']],
                'close': [position['entry_price']],
                'volume': [0]
            }, index=[position['entry_time']])

            mock_md = {symbol: mock_df}

            # Получаем стратегию для расчета стоп-лосса
            if hasattr(self.context.strategy, 'legacy'):
                # Это адаптер, используем legacy стратегию
                strategy = self.context.strategy.legacy
            else:
                strategy = self.context.strategy

            # Рассчитываем стоп-лосс
            if hasattr(strategy, 'calculate_stop_loss_price'):
                side = 'long' if position['side'] == 'BUY' else 'short'
                stop_loss_price = strategy.calculate_stop_loss_price(
                    position['entry_price'],
                    side,
                    symbol
                )

                if stop_loss_price is not None:
                    position['stop_loss'] = stop_loss_price
                    print(f"🎯 [BACKTEST] Set initial stop loss: {stop_loss_price:.4f} for position {symbol}")

                    # Set initial max_price/min_price for trailing stop
                    position['max_price'] = position['entry_price']
                    position['min_price'] = position['entry_price']

        except Exception as e:
            print(f"⚠️ [BACKTEST] Error setting stop loss: {e}")

    async def _update_trailing_stops(self, current_md: MarketData, current_time):
        """Обновляет trailing stop для всех открытых позиций"""
        for symbol, position in self.context.open_positions.items():
            if symbol not in current_md:
                continue

            df = current_md[symbol]
            if df.empty:
                continue

            current_price = df['close'].iloc[-1]

            # Check if trailing stop needs update
            await self._update_single_trailing_stop(position, current_price, symbol)

    async def _update_single_trailing_stop(self, position: Dict, current_price: float, symbol: str):
        """Обновляет trailing stop для одной позиции"""
        if 'stop_loss' not in position or position['stop_loss'] is None:
            return

        side = position['side']
        entry_price = position['entry_price']

        # Update max_price/min_price for tracking extremes
        if side == 'BUY':
            if 'max_price' not in position or current_price > position.get('max_price', entry_price):
                position['max_price'] = current_price
                max_price = current_price
            else:
                max_price = position.get('max_price', entry_price)
        else:  # SELL
            if 'min_price' not in position or current_price < position.get('min_price', entry_price):
                position['min_price'] = current_price
                min_price = current_price
            else:
                min_price = position.get('min_price', entry_price)

        # Check if trailing stop needs update
        should_update = self._should_update_trailing_stop(position, current_price)
        if should_update:
            new_stop_price = self._calculate_trailing_stop_price(position, current_price)
            if new_stop_price is not None:
                old_stop = position['stop_loss']
                position['stop_loss'] = new_stop_price
                print(f"📈 [BACKTEST] Updated trailing stop: {old_stop:.4f} -> {new_stop_price:.4f}")

    def _should_update_trailing_stop(self, position: Dict, current_price: float) -> bool:
        """Проверяет, нужно ли обновлять trailing stop"""
        side = position['side']

        if side == 'BUY':
            # For long, update if price is above current max
            max_price = position.get('max_price', position['entry_price'])
            return current_price > max_price
        else:
            # For short, update if price is below current min
            min_price = position.get('min_price', position['entry_price'])
            return current_price < min_price

    def _calculate_trailing_stop_price(self, position: Dict, current_price: float) -> Optional[float]:
        """Рассчитывает новую цену trailing stop"""
        # Используем trailing_stop_pct из контекста или дефолтное значение
        trailing_pct = self.context.config.get('trailing_stop_pct', 0.005)  # 0.5% по умолчанию

        side = position['side']

        if side == 'BUY':
            # For long: stop loss below current price
            return current_price * (1 - trailing_pct)
        else:
            # For short: stop loss above current price
            return current_price * (1 + trailing_pct)

    def _close_position(self, symbol: str, position: Dict, exit_price: float, current_time, reason: str):
        """Закрыть позицию"""
        # Calculate PnL
        pnl = self._calculate_pnl(position, exit_price)
        pnl_pct = self._calculate_pnl_pct(position, exit_price)

        # Close fee
        close_fee = abs(exit_price * position['size']) * self.context.fee_rate

        # Update balance
        self.context.current_balance += pnl - close_fee

        # Add closing trade
        close_trade = {
            'symbol': symbol,
            'side': 'long' if position['side'] == 'BUY' else 'short',
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'entry_time': position['entry_time'],
            'exit_time': current_time,
            'size': position['size'],
            'leverage': self.context.leverage,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'fee_close': close_fee,
            'reason': reason,
            'status': 'closed'
        }

        self.context.trades.append(close_trade)

        # Remove position
        del self.context.open_positions[symbol]

        print(f"💰 CLOSED position: {position['side']} {symbol} @ ${exit_price:.2f} (PnL: ${pnl:.2f})")
        
        
    def _calculate_pnl(self, position: Dict, exit_price: float) -> float:
        """Расчет прибыли/убытка"""
        entry_price = position['entry_price']
        size = position['size']
        side = position['side']
        leverage = position.get('leverage', 1)

        if side == 'BUY':
            return (exit_price - entry_price) * size * leverage
        else:
            return (entry_price - exit_price) * size * leverage

    def _calculate_pnl_pct(self, position: Dict, exit_price: float) -> float:
        """Расчет прибыли/убытка в процентах"""
        entry_price = position['entry_price']
        side = position['side']
        leverage = position.get('leverage', 1)

        if entry_price == 0:
            return 0.0

        if side == 'BUY':
            return (exit_price - entry_price) / entry_price * leverage
        else:
            return (entry_price - exit_price) / entry_price * leverage

    def _update_equity_curve(self, current_time):
        """Обновить кривую доходности"""
        # Calculate unrealized PnL
        unrealized_pnl = 0.0

        if self.context.open_positions:
            # Get current prices
            current_prices = {}
            for symbol, df in self.context.market_data.items():
                if not df.empty and symbol in self.context.open_positions:
                    # Find price at current moment or previous one
                    mask = df.index <= current_time
                    if mask.any():
                        current_prices[symbol] = df[mask]['close'].iloc[-1]

            for symbol, position in self.context.open_positions.items():
                if symbol in current_prices:
                    price = current_prices[symbol]
                    unrealized_pnl += self._calculate_pnl(position, price)

        # Add point to equity curve
        self.context.equity_curve.append(
            BacktestEquityPoint(
                timestamp=current_time,
                balance=self.context.current_balance + unrealized_pnl
            )
        )

    def _build_result(self) -> BacktestResult:
        """Сформировать результат бэктеста"""
        # Calculate statistics
        stats = self._calculate_statistics()

        # Format trades to match BacktestTrade schema
        formatted_trades = self._format_trades_for_result()


        # Merge backtest config parameters and strategy parameters
        merged_parameters = self.context.config.copy()
        if hasattr(self.context.template, 'parameters') and self.context.template.parameters:
            merged_parameters.update(self.context.template.parameters)

        return BacktestResult(
            strategy_name=self.context.strategy.id,
            symbol=", ".join(self.get_required_symbols()),
            template_id=self.context.template.id,
            start_date=self.timeline[0] if self.timeline else datetime.now(),
            end_date=self.timeline[-1] if self.timeline else datetime.now(),
            initial_balance=self.context.initial_balance,
            final_balance=self.context.current_balance,
            trades=formatted_trades,
            equity_curve=self.context.equity_curve,
            parameters=self.context.template.parameters or {},
            leverage=self.context.leverage,
            **stats
        )

    def _format_trades_for_result(self) -> List[BacktestTrade]:
        """Форматирование сделок для соответствия схеме BacktestTrade"""
        formatted_trades = []

        for trade in self.context.trades:
            # В результаты отправляем только закрытые сделки
            if trade.get('status') == 'closed':
                formatted_trade = BacktestTrade(
                    entry_time=trade['entry_time'],
                    exit_time=trade.get('exit_time'),
                    entry_price=trade['entry_price'],
                    exit_price=trade.get('exit_price'),
                    side=trade.get('side'),
                    size=trade['size'],
                    pnl=trade.get('pnl'),
                    pnl_pct=trade.get('pnl_pct'),
                    reason=trade.get('reason', 'unknown'),
                    symbol=trade['symbol'],
                    leverage=trade.get('leverage', self.context.leverage),
                    status=trade.get('status', 'unknown')
                )
                formatted_trades.append(formatted_trade)
            # Открытые сделки игнорируем

        return formatted_trades

    def _calculate_statistics(self) -> Dict[str, Any]:
        """Расчет статистик бэктеста"""
        closed_trades = [t for t in self.context.trades if t.get('status') == 'closed']

        if not closed_trades:
            return {
                'total_pnl': 0.0,
                'total_pnl_pct': 0.0,
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'sharpe_ratio': 0.0
            }

        # Calculate total profitability
        total_pnl = self.context.current_balance - self.context.initial_balance
        total_pnl_pct = (total_pnl / self.context.initial_balance) * 100 if self.context.initial_balance > 0 else 0.0

        # Win rate and trade statistics
        winning_trades = [t for t in closed_trades if t['pnl'] > 0]
        losing_trades = [t for t in closed_trades if t['pnl'] < 0]

        winning_count = len(winning_trades)
        losing_count = len(losing_trades)
        total_trades_count = len(closed_trades)

        win_rate = (winning_count / total_trades_count * 100) if total_trades_count > 0 else 0.0

        # Average winning and losing trades
        avg_win = sum(t['pnl'] for t in winning_trades) / winning_count if winning_count > 0 else 0.0
        avg_loss = abs(sum(t['pnl'] for t in losing_trades) / losing_count) if losing_count > 0 else 0.0

        # Profit factor (избегаем Infinity/NaN)
        gross_profit = sum(t['pnl'] for t in winning_trades)
        gross_loss = abs(sum(t['pnl'] for t in losing_trades))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            # Если нет убытков, задаем 0.0 (или 1.0). Используем 0.0 для совместимости с JSON/валидацией
            profit_factor = 0.0

        # Max drawdown
        max_drawdown = self._calculate_max_drawdown()
        max_drawdown_pct = (max_drawdown / self.context.initial_balance) * 100 if self.context.initial_balance > 0 else 0.0

        # Sharpe ratio (simplified version)
        sharpe_ratio = 0.0  # Requires more data for calculation

        return {
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'total_trades': total_trades_count,
            'winning_trades': winning_count,
            'losing_trades': losing_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio
        }

    def _calculate_max_drawdown(self) -> float:
        """Расчет максимальной просадки"""
        if not self.context.equity_curve:
            return 0.0

        balances = [point.balance for point in self.context.equity_curve]
        peak = balances[0]
        max_drawdown = 0.0

        for balance in balances:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak * 100 if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown