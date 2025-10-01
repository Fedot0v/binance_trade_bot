from __future__ import annotations

from typing import Dict, Any, List
import pandas as pd

from schemas.backtest import BacktestResult, BacktestEquityPoint
from services.backtest.result_builder import ResultBuilder
from services.backtest.decision_policy import (
    should_analyze_compensation_entry,
    build_open_state,
)


class DualBacktestOrchestrator:
    def __init__(self, position_manager, backtest_executor, stats_service, data_feed):
        self.position_manager = position_manager
        self.backtest_executor = backtest_executor
        self.stats_service = stats_service
        self.data_feed = data_feed
        self.result_builder = ResultBuilder(stats_service)

    async def execute(
        self,
        btc_data: pd.DataFrame,
        eth_data: pd.DataFrame,
        initial_balance: float,
        strategy,
        strategy_name: str,
        symbol1: str,
        symbol2: str,
        parameters: Dict[str, Any],
        template,
    ) -> BacktestResult:
        balance = initial_balance
        equity_curve: List[BacktestEquityPoint] = [BacktestEquityPoint(timestamp=btc_data.index[0], balance=balance)]
        trades: List[Dict[str, Any]] = []
        open_positions: Dict[str, Dict[str, Any]] = {}
        pending_opens: List[Any] = []

        print(f"\n🚀 ЗАПУСК КОМПЕНСАЦИОННОГО БЕКТЕСТА (dual): {strategy_name}")
        # Сброс состояния стратегии перед началом бэктеста (если поддерживается)
        try:
            strategy_obj = getattr(strategy, 'strategy', strategy)
            if hasattr(strategy_obj, 'reset_state') and callable(getattr(strategy_obj, 'reset_state')):
                strategy_obj.reset_state()
        except Exception:
            pass
        for step in self.data_feed.iter_dual(btc_data, eth_data, symbol1, symbol2, warmup=0):
            i = step['index']
            current_time = step['time']
            md = step['md']
            btc_current_price = step['prices'][symbol1]
            eth_current_price = step['prices'][symbol2]
            btc_open = float(md[symbol1]['open'].iloc[-1]) if 'open' in md[symbol1].columns else btc_current_price
            eth_open = float(md[symbol2]['open'].iloc[-1]) if 'open' in md[symbol2].columns else eth_current_price

            if i % 100 == 0:
                print(f"⏰ Время: {current_time}, Свеча: {i}/{len(btc_data)}, Баланс: ${balance:,.2f}")
                print(f"  🔍 Открытые позиции: {len(open_positions)}")

            initial_positions_count = len(open_positions)

            # 1) Исполняем отложенные открытия по open текущей свечи
            if pending_opens:
                to_execute = pending_opens
                pending_opens = []
                for intent in to_execute:
                    price = btc_open if intent.symbol == symbol1 else eth_open
                    if self.backtest_executor.can_open_position(intent, open_positions, balance):
                        trade_result = self.backtest_executor.execute(
                            intent=intent,
                            current_price=price,
                            current_time=current_time,
                            balance=balance,
                            symbol=intent.symbol,
                        )
                        if trade_result:
                            balance = trade_result['new_balance']
                            try:
                                leverage_val = float(getattr(template, 'leverage', 1) or 1)
                            except Exception:
                                leverage_val = 1.0
                            stop_loss_price = None
                            take_profit_price = None
                            try:
                                strategy_obj = getattr(strategy, 'strategy', strategy)

                                # Нормализуем сторону для методов стратегии
                                side_upper = str(intent.side).upper()
                                side_alias_for_strategy = 'long' if side_upper in ('BUY', 'LONG') else 'short'

                                if hasattr(strategy_obj, 'calculate_stop_loss_price'):
                                    stop_loss_price = strategy_obj.calculate_stop_loss_price(
                                        trade_result['price'], side_alias_for_strategy, intent.symbol
                                    )
                                # Рассчитываем TP
                                if hasattr(strategy_obj, 'calculate_take_profit_price'):
                                    take_profit_price = strategy_obj.calculate_take_profit_price(
                                        trade_result['price'], side_alias_for_strategy, intent.symbol
                                    )
                                # Фолбэк, если методы отсутствуют или вернули None
                                if stop_loss_price is None:
                                    stop_loss_price = trade_result['price'] * (0.98 if intent.side == 'BUY' else 1.02)
                                if take_profit_price is None:
                                    take_profit_price = trade_result['price'] * (1.03 if intent.side == 'BUY' else 0.97)
                            except Exception:
                                # На крайний случай — жёсткие дефолты
                                stop_loss_price = trade_result['price'] * (0.98 if intent.side == 'BUY' else 1.02)
                                take_profit_price = trade_result['price'] * (1.03 if intent.side == 'BUY' else 0.97)
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
            balance = self.position_manager.check_and_close_positions_sync(
                open_positions, md, current_time, balance, trades, strategy=strategy
            )

            # Всегда спрашиваем стратегию (для обработки закрытий и компенсаций)
            if hasattr(strategy, 'decide'):
                open_state = build_open_state(open_positions)
                
                # Логируем состояние для отладки
                if i % 50 == 0:
                    print(f"🔍 Анализ стратегии на свече {i}:")
                    print(f"  📊 Открытые позиции: {len(open_state)}")
                    print(f"  💰 Баланс: ${balance:,.2f}")
                    if open_state:
                        for sym, pos in open_state.items():
                            print(f"  📈 {sym}: {pos.side} @ ${pos.entry_price:,.2f}")
                
                decision = await strategy.decide(md, template, open_state)
                if decision and not decision.is_empty():
                    print(f"🎯 Стратегия приняла решение: {len(decision.intents)} намерений")
                    for intent in list(decision.intents):
                        print(f"  📋 Намерение: {intent.symbol} {intent.side} {intent.sizing}")
                        if intent.sizing == "close":
                            if intent.symbol in open_positions:
                                position = open_positions[intent.symbol]
                                current_price = btc_current_price if intent.symbol == symbol1 else eth_current_price
                                pnl = self.position_manager.calculate_pnl(position, current_price)
                                pnl_pct = self.position_manager.calculate_pnl_pct(position, current_price)
                                close_fee = current_price * position['size'] * self.position_manager.fee_rate
                                new_balance = balance + pnl - close_fee
                                trades.append({
                                    'symbol': intent.symbol,
                                    'side': 'long' if position['side'] == 'BUY' else 'short',
                                    'entry_price': position['entry_price'],
                                    'exit_price': current_price,
                                    'entry_time': position['entry_time'],
                                    'exit_time': current_time,
                                    'size': position['size'],
                                    'pnl': pnl,
                                    'pnl_pct': pnl_pct,
                                    'fee_close': close_fee,
                                    'reason': 'strategy_signal',
                                })
                                balance = new_balance
                                del open_positions[intent.symbol]
                                print(f"✅ Закрыта позиция {intent.symbol}: PnL ${pnl:,.2f}")
                        else:
                            # Жёсткая защита: не допускать открытия ETH раньше BTC
                            try:
                                is_eth_open_intent = (intent.symbol == symbol2)
                                if is_eth_open_intent:
                                    btc_is_open = (symbol1 in open_positions)
                                    allow_post_window = False
                                    try:
                                        strategy_obj = getattr(strategy, 'strategy', strategy)
                                        if hasattr(strategy_obj, 'can_compensate_after_close'):
                                            had_btc = bool(getattr(getattr(strategy_obj, 'state', None), 'had_btc', False))
                                            allow_post_window = had_btc and bool(strategy_obj.can_compensate_after_close(current_time))
                                    except Exception:
                                        allow_post_window = False

                                    if not btc_is_open and not allow_post_window:
                                        print("⛔ Пропускаем ETH открытие: BTC не открыт и пост-окно компенсации недоступно")
                                        continue
                            except Exception:
                                pass

                            # Открытия откладываем
                            pending_opens.append(intent)
                            print(f"📝 Отложено открытие: {intent.symbol} {intent.side} (будет исполнено на следующей свече)")
                else:
                    if i % 50 == 0:
                        print(f"🤔 Стратегия не приняла решений на свече {i}")

            # Mark-to-market equity
            unrealized = 0.0
            if open_positions:
                for sym, pos in open_positions.items():
                    px = btc_current_price if sym == symbol1 else eth_current_price
                    unrealized += self.position_manager.calculate_pnl(pos, px)
            equity_curve.append(BacktestEquityPoint(timestamp=current_time, balance=balance + unrealized))

        if open_positions:
            for symbol, position in list(open_positions.items()):
                last_price = btc_data['close'].iloc[-1] if symbol == symbol1 else eth_data['close'].iloc[-1]
                pnl = self.position_manager.calculate_pnl(position, last_price)
                pnl_pct = self.position_manager.calculate_pnl_pct(position, last_price)
                new_balance = balance + pnl
                trades.append({
                    'symbol': symbol,
                    'side': 'long' if position['side'] == 'BUY' else 'short',
                    'entry_price': position['entry_price'],
                    'exit_price': last_price,
                    'entry_time': position['entry_time'],
                    'exit_time': btc_data.index[-1],
                    'size': position['size'],
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'new_balance': new_balance,
                    'reason': 'end_of_data',
                })
                balance = new_balance

        return self.result_builder.build(
            strategy_name=strategy_name,
            symbol=f"{symbol1}+{symbol2}",
            start_date=btc_data.index[0],
            end_date=btc_data.index[-1],
            initial_balance=initial_balance,
            final_balance=balance,
            trades=trades,
            equity_curve=equity_curve,
            parameters=parameters,
        )


