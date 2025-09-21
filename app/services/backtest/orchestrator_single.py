from __future__ import annotations

from typing import Dict, Any, List
import pandas as pd

from schemas.backtest import BacktestResult, BacktestEquityPoint
from services.backtest.result_builder import ResultBuilder
from services.backtest.decision_policy import should_analyze_for_entry, build_open_state


class SingleBacktestOrchestrator:
    def __init__(self, position_manager, backtest_executor, stats_service, data_feed):
        self.position_manager = position_manager
        self.backtest_executor = backtest_executor
        self.stats_service = stats_service
        self.data_feed = data_feed
        self.result_builder = ResultBuilder(stats_service)

    async def execute(
        self,
        data: pd.DataFrame,
        initial_balance: float,
        strategy,
        strategy_name: str,
        symbol: str,
        parameters: Dict[str, Any],
        template,
        leverage: int = 1,
    ) -> BacktestResult:
        balance = initial_balance
        trades: List[Dict[str, Any]] = []
        equity_curve: List[BacktestEquityPoint] = []
        open_positions: Dict[str, Dict[str, Any]] = {}
        pending_opens: List[Any] = []  # intents, будут исполнены на открытии следующей свечи

        print(f"\n🚀 ЗАПУСК БЕКТЕСТА (single): {strategy_name}")
        print(f"📊 Символ: {symbol}")
        print(f"💰 Начальный баланс: ${initial_balance:,.2f}")
        print(f"📈 Количество свечей: {len(data)}")
        print(f"⚙️ Параметры: {parameters}")

        for step in self.data_feed.iter_single(data, symbol=symbol, warmup=100):
            i = step['index']
            current_time = step['time']
            md = step['md']
            current_price = step['prices'][symbol]
            # Цена открытия текущей свечи для исполнения отложенных открытий
            current_open = float(md[symbol]['open'].iloc[-1]) if 'open' in md[symbol].columns else current_price

            if i % 100 == 0:
                print(f"⏰ Время: {current_time}, Свеча: {i}/{len(data)}, Баланс: ${balance:,.2f}")
                print(f"  🔍 Открытые позиции: {len(open_positions)}")

            # 1) Исполняем отложенные открытия по open текущей свечи
            if pending_opens:
                to_execute = pending_opens
                pending_opens = []
                for intent in to_execute:
                    if intent.symbol != symbol:
                        continue
                    if self.backtest_executor.can_open_position(intent, open_positions, balance):
                        trade_result = self.backtest_executor.execute(
                            intent=intent,
                            current_price=current_open,
                            current_time=current_time,
                            balance=balance,
                            symbol=intent.symbol,
                        )
                        if trade_result:
                            balance = trade_result['new_balance']
                            # плечо берем из шаблона, если доступно
                            try:
                                leverage_val = float(getattr(template, 'leverage', 1) or 1)
                            except Exception:
                                leverage_val = 1.0
                            # рассчитать SL/TP через стратегию, если доступно
                            stop_loss_price = None
                            take_profit_price = None
                            try:
                                side_upper = str(intent.side).upper()
                                strategy_side = 'long' if side_upper in ('BUY', 'LONG') else 'short'

                                if hasattr(strategy, 'calculate_stop_loss_price'):
                                    stop_loss_price = strategy.calculate_stop_loss_price(trade_result['price'], strategy_side, intent.symbol)
                                    if stop_loss_price is None:
                                        stop_loss_price = trade_result['price'] * (0.98 if strategy_side == 'long' else 1.02)

                                if hasattr(strategy, 'calculate_take_profit_price'):
                                    take_profit_price = strategy.calculate_take_profit_price(trade_result['price'], strategy_side, intent.symbol)
                                    if take_profit_price is None:
                                        take_profit_price = trade_result['price'] * (1.03 if strategy_side == 'long' else 0.97)
                            except Exception:
                                pass
                            open_positions[intent.symbol] = {
                                'deal_id': len(trades),
                                'entry_price': trade_result['price'],
                                'entry_time': current_time,
                                'side': intent.side,
                                'size': trade_result['size'],
                                'symbol': intent.symbol,
                                'leverage': leverage_val,
                                'entry_size_usd': trade_result.get('size_usd'),
                                'stop_loss': stop_loss_price,
                                'take_profit': take_profit_price,
                                # Инициализируем max_price и min_price для trailing stop
                                'max_price': trade_result['price'],  # Для LONG позиции
                                'min_price': trade_result['price'],  # Для SHORT позиции
                            }
                            print(f"💰 ОТКРЫТА позиция (отлож.): {intent.side} {intent.symbol} @ ${trade_result['price']:.2f}")

            balance = await self.position_manager.check_and_close_positions_async(
                open_positions, md, current_time, balance, trades, strategy=strategy
            )

            # Всегда спрашиваем стратегию (для обработки закрытий)
            if hasattr(strategy, 'decide'):
                open_state = build_open_state(open_positions)
                decision = await strategy.decide(md, template, open_state)
                if decision and not decision.is_empty():
                    print(f"🎯 Сигналы стратегии на свече {i}: {decision}")
                    for intent in decision.intents:
                        if intent.symbol != symbol:
                            continue
                        if intent.sizing == 'close':
                            # Закрытие по сигналу стратегии
                            if intent.symbol in open_positions:
                                position = open_positions[intent.symbol]
                                exit_price = float(md[intent.symbol]['close'].iloc[-1])
                                pnl = self.position_manager.calculate_pnl(position, exit_price)
                                pnl_pct = self.position_manager.calculate_pnl_pct(position, exit_price)
                                close_fee = exit_price * position['size'] * self.position_manager.fee_rate
                                balance = balance + pnl - close_fee
                                trades.append({
                                    'symbol': intent.symbol,
                                    'side': 'long' if position['side'] == 'BUY' else 'short',
                                    'entry_price': position['entry_price'],
                                    'exit_price': exit_price,
                                    'entry_time': position['entry_time'],
                                    'exit_time': current_time,
                                    'size': position['size'],
                                    'pnl': pnl,
                                    'pnl_pct': pnl_pct,
                                    'fee_close': close_fee,
                                    'reason': 'strategy_signal',
                                })
                                del open_positions[intent.symbol]
                        else:
                            # Открытия откладываем на следующую свечу
                            pending_opens.append(intent)
            else:
                # Поддержка альтернативных стратегий
                pass

            # Mark-to-market equity: баланс + нереализованный PnL по открытым позициям
            unrealized = 0.0
            if open_positions:
                for sym, pos in open_positions.items():
                    price = float(md[sym]['close'].iloc[-1])
                    unrealized += self.position_manager.calculate_pnl(pos, price)
            equity_curve.append(BacktestEquityPoint(timestamp=current_time, balance=balance + unrealized))

        # Закрытие остаточных позиций
        if open_positions:
            print(f"\n🔚 ЗАКРЫТИЕ ОСТАВШИХСЯ ПОЗИЦИЙ:")
            last_price = data['close'].iloc[-1]
            for sym, pos in list(open_positions.items()):
                pnl = self.position_manager.calculate_pnl(pos, last_price)
                pnl_pct = self.position_manager.calculate_pnl_pct(pos, last_price)
                balance = balance + pnl
                trades.append({
                    'symbol': sym,
                    'side': 'long' if pos['side'] == 'BUY' else 'short',
                    'entry_price': pos['entry_price'],
                    'exit_price': last_price,
                    'entry_time': pos['entry_time'],
                    'exit_time': data.index[-1],
                    'size': pos['size'],
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'reason': 'end_of_data',
                })

        return self.result_builder.build(
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=data.index[0],
            end_date=data.index[-1],
            initial_balance=initial_balance,
            final_balance=balance,
            trades=trades,
            equity_curve=equity_curve,
            parameters=parameters,
            leverage=leverage,
        )


