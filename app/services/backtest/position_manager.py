from __future__ import annotations

from typing import Dict, List, Tuple, Any


class PositionManager:
    """Отвечает за жизненный цикл позиций: условия закрытия, расчет PnL и комиссий.

    intrabar_mode управляет порядком обработки, если в одной свече задеты и SL, и TP:
      - 'stopfirst' (по умолчанию): считаем, что сначала сработает стоп-лосс (консервативно)
      - 'tpfirst': считаем, что сначала достигнем тейк-профита (оптимистично)
      - 'mid': выбираем ближайшую к цене открытия текущей свечи цель
    """

    def __init__(self, fee_rate: float = 0.0004, intrabar_mode: str = 'stopfirst') -> None:
        self.fee_rate = fee_rate
        self.intrabar_mode = intrabar_mode

    def calculate_pnl(self, position: Dict[str, Any], current_price: float) -> float:
        entry_price = position['entry_price']
        size = position['size']
        side = position['side']
        leverage = position.get('leverage', 1)

        if side == 'BUY':
            return (current_price - entry_price) * size * leverage
        return (entry_price - current_price) * size * leverage

    def calculate_pnl_pct(self, position: Dict[str, Any], current_price: float) -> float:
        entry_price = position['entry_price']
        side = position['side']
        leverage = position.get('leverage', 1)
        if entry_price == 0:
            return 0.0
        if side == 'BUY':
            return (current_price - entry_price) / entry_price * leverage
        return (entry_price - current_price) / entry_price * leverage

    def check_close_conditions(self, position: Dict[str, Any], ohlc: Dict[str, float], current_time) -> Tuple[bool, str, float]:
        """
        Проверяет условия закрытия позиции по OHLC свечи
        Возвращает (нужно_закрыть, причина, цена_выхода)
        """
        open_price = ohlc['open']
        high_price = ohlc['high']
        low_price = ohlc['low']
        close_price = ohlc['close']
        
        # Проверяем SL/TP если они заданы
        sl_price = position.get('stop_loss')
        tp_price = position.get('take_profit')
        
        if sl_price is not None or tp_price is not None:
            sl_hit = False
            tp_hit = False
            
            if sl_price is not None:
                if position['side'] == 'BUY':
                    sl_hit = low_price <= sl_price  # Для лонга: low свечи задел SL
                else:
                    sl_hit = high_price >= sl_price  # Для шорта: high свечи задел SL
                    
            if tp_price is not None:
                if position['side'] == 'BUY':
                    tp_hit = high_price >= tp_price  # Для лонга: high свечи задел TP
                else:
                    tp_hit = low_price <= tp_price  # Для шорта: low свечи задел TP
            
            if sl_hit and tp_hit:
                if self.intrabar_mode == 'tpfirst':
                    return True, 'take_profit', tp_price if tp_price is not None else close_price
                if self.intrabar_mode == 'mid':
                    # выбираем ближе к open
                    cand = []
                    if sl_price is not None:
                        cand.append(('stop_loss', sl_price, abs(sl_price - open_price)))
                    if tp_price is not None:
                        cand.append(('take_profit', tp_price, abs(tp_price - open_price)))
                    if cand:
                        cand.sort(key=lambda x: x[2])
                        return True, cand[0][0], cand[0][1]
                # default stopfirst
                return True, 'stop_loss', sl_price if sl_price is not None else close_price
            if sl_hit:
                return True, 'stop_loss', sl_price if sl_price is not None else close_price
            if tp_hit:
                return True, 'take_profit', tp_price if tp_price is not None else close_price

        # Если SL/TP не заданы — стратегия должна управлять закрытием сама
        # Но в бэктесте мы все равно должны проверять базовые условия
        return False, '', close_price

    async def check_and_close_positions_async(
        self,
        open_positions: Dict[str, Dict[str, Any]],
        market_data: Dict[str, Any],
        current_time,
        balance: float,
        trades: List[Dict[str, Any]],
        strategy=None
    ) -> float:
        if not open_positions:
            return balance

        positions_to_close: List[Tuple[str, Dict[str, Any], str, float]] = []
        for symbol, position in open_positions.items():
            if symbol not in market_data:
                continue
            last_row = market_data[symbol].iloc[-1]
            ohlc = {
                'open': float(last_row['open']) if 'open' in last_row else float(position['entry_price']),
                'high': float(last_row['high']) if 'high' in last_row else float(position['entry_price']),
                'low': float(last_row['low']) if 'low' in last_row else float(position['entry_price']),
                'close': float(last_row['close']) if 'close' in last_row else float(position['entry_price']),
            }

            try:
                # Обновляем экстремумы для трейлинга
                if position.get('side') == 'BUY':
                    position['max_price'] = max(position.get('max_price', position['entry_price']), ohlc['high'])
                else:
                    position['min_price'] = min(position.get('min_price', position['entry_price']), ohlc['low'])

                # Рассчитываем трейлинг-стоп через стратегию, если доступно
                if strategy and hasattr(strategy, 'calculate_trailing_stop_price'):
                    try:
                        # Создаем адаптер позиции для совместимости с BaseStrategy
                        class PositionAdapter:
                            def __init__(self, position_dict):
                                self.entry_price = position_dict['entry_price']
                                self.side = position_dict['side']
                                self.max_price = position_dict.get('max_price', position_dict['entry_price'])
                                self.min_price = position_dict.get('min_price', position_dict['entry_price'])

                        position_adapter = PositionAdapter(position)

                        # Проверяем, нужно ли обновлять trailing stop
                        if hasattr(strategy, 'legacy') and hasattr(strategy.legacy, 'should_update_trailing_stop'):
                            # Это NovichokAdapter - используем метод через legacy
                            should_update = strategy.legacy.should_update_trailing_stop(position_adapter, ohlc['close'])
                        elif hasattr(strategy, 'should_update_trailing_stop'):
                            # Прямой вызов метода
                            should_update = strategy.should_update_trailing_stop(position_adapter, ohlc['close'])
                        else:
                            should_update = True  # Если метода нет, обновляем всегда

                        if not should_update:
                            continue

                        # Определяем правильную сигнатуру метода
                        if hasattr(strategy, 'legacy') and hasattr(strategy.legacy, 'calculate_trailing_stop_price'):
                            # Это NovichokAdapter - используем сигнатуру NovichokStrategy
                            side_str = 'long' if position['side'] == 'BUY' else 'short'
                            new_stop = strategy.legacy.calculate_trailing_stop_price(
                                position['entry_price'],
                                ohlc['close'],
                                side_str,
                                symbol
                            )
                        elif hasattr(strategy, 'calculate_trailing_stop_price'):
                            # Проверяем сигнатуру BaseStrategy
                            if len(strategy.calculate_trailing_stop_price.__code__.co_varnames) == 3:
                                # BaseStrategy сигнатура: (deal, current_price)
                                new_stop = strategy.calculate_trailing_stop_price(position_adapter, ohlc['close'])
                            else:
                                # Другая сигнатура
                                side_str = 'long' if position['side'] == 'BUY' else 'short'
                                new_stop = strategy.calculate_trailing_stop_price(
                                    position['entry_price'],
                                    ohlc['close'],
                                    side_str,
                                    symbol
                                )
                        else:
                            new_stop = None

                        if new_stop is not None:
                            # Обновляем фактический стоп-лосс уровнем трейлинга
                            position['stop_loss'] = new_stop
                            print(f"📈 Обновлен trailing stop: {new_stop:.4f}")
                    except Exception as e:
                        print(f"⚠️  Ошибка обновления trailing stop: {e}")
                        pass
            except Exception:
                pass

            should_close, reason, exit_price = self.check_close_conditions(position, ohlc, current_time)
            if should_close:
                positions_to_close.append((symbol, position, reason, exit_price))

        for symbol, position, reason, exit_price in positions_to_close:
            if symbol not in market_data:
                continue
            pnl = self.calculate_pnl(position, exit_price)
            pnl_pct = self.calculate_pnl_pct(position, exit_price)
            close_fee = exit_price * position['size'] * self.fee_rate
            new_balance = balance + pnl - close_fee

            close_trade = {
                'symbol': symbol,
                'side': 'long' if position['side'] == 'BUY' else 'short',
                'entry_price': position['entry_price'],
                'exit_price': exit_price,
                'entry_time': position['entry_time'],
                'exit_time': current_time,
                'size': position['size'],
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'fee_close': close_fee,
                'reason': reason,
            }

            trades.append(close_trade)
            balance = new_balance
            del open_positions[symbol]

        return balance

    def check_and_close_positions_sync(
        self,
        open_positions: Dict[str, Dict[str, Any]],
        market_data: Dict[str, Any],
        current_time,
        balance: float,
        trades: List[Dict[str, Any]],
        strategy=None
    ) -> float:
        # Переиспользуем асинхронную логику без await
        # Внутри нет реальных await, поэтому можно вызывать напрямую
        return _sync_wrapper(self.check_and_close_positions_async,
                             open_positions, market_data, current_time, balance, trades, strategy)


def _sync_wrapper(coro_fn, *args, **kwargs):
    # Выполняем корутину синхронно (без реального event loop, т.к. await не используется внутри)
    coro = coro_fn(*args, **kwargs)
    try:
        return coro.send(None)
    except StopIteration as e:
        return e.value


