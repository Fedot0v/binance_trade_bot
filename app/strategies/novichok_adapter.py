from typing import Dict, List, Any

import pandas as pd

from strategies.contracts import Decision, OrderIntent


def _sym_str(x) -> str:
    return x.value if hasattr(x, "value") else str(x)


class NovichokAdapter:
    """
    Wrapper for Novichok strategy
    """

    id = "novichok-adapter"

    def __init__(self, legacy_novichok):
        self.legacy = legacy_novichok

    def required_symbols(self, template) -> List[str]:
        return [_sym_str(getattr(template, "symbol", "BTCUSDT"))]

    async def decide(
        self,
        md: Dict[str, pd.DataFrame],
        template,
        open_state: Dict[str, Any] | None = None
    ) -> Decision:
        symbol = self.required_symbols(template)[0]

        df = md.get(symbol)
        if df is None or df.empty:
            return Decision(intents=[])

        signal = self.legacy.generate_signal(df)

        if signal in (None, "hold"):
            return Decision(intents=[])

        side = "BUY" if signal == "long" else "SELL"

        risk_pct = float(getattr(
            template,
            "deposit_prct", 
            getattr(self.legacy, "deposit_prct", 0.01)  # дефолт в долях
            )
        )

        if open_state and symbol in open_state:
            pos = open_state[symbol]['position'] if 'position' in open_state[symbol] else None
            if pos:
                pos_side = pos.get('side')
                entry_price = pos.get('entry_price')
                current_price = df['close'].iloc[-1]

                strategy_side = 'long' if pos_side == 'BUY' else 'short'
                stop_loss_price = self.legacy.calculate_stop_loss_price(entry_price, strategy_side, symbol)
                # Проверяем, что stop_loss_price не None
                if stop_loss_price is None:
                    stop_loss_price = entry_price * (0.98 if strategy_side == 'long' else 1.02)

                stop_loss_triggered = (
                    (pos_side == 'BUY' and current_price <= stop_loss_price) or
                    (pos_side == 'SELL' and current_price >= stop_loss_price)
                )

                if stop_loss_triggered:
                    close_intent = OrderIntent(
                        symbol=symbol,
                        side='SELL' if pos_side == 'BUY' else 'BUY',
                        sizing='close',
                        size=0,
                        role='close'
                    )
                    print(f"🛑 NovichokAdapter: СТОП-ЛОСС! Цена {current_price:.2f} {'ниже' if pos_side == 'BUY' else 'выше'} уровня {stop_loss_price:.2f}")
                    return Decision(intents=[close_intent])

                take_profit_price = self.legacy.calculate_take_profit_price(entry_price, strategy_side, symbol)
                # Проверяем, что take_profit_price не None
                if take_profit_price is None:
                    take_profit_price = entry_price * (1.03 if strategy_side == 'long' else 0.97)

                take_profit_triggered = (
                    (pos_side == 'BUY' and current_price >= take_profit_price) or
                    (pos_side == 'SELL' and current_price <= take_profit_price)
                )

                if take_profit_triggered:
                    close_intent = OrderIntent(
                        symbol=symbol,
                        side='SELL' if pos_side == 'BUY' else 'BUY',
                        sizing='close',
                        size=0,
                        role='close'
                    )
                    print(f"🎯 NovichokAdapter: ТЕЙК-ПРОФИТ! Цена {current_price:.2f} {'выше' if pos_side == 'BUY' else 'ниже'} уровня {take_profit_price:.2f}")
                    return Decision(intents=[close_intent])

                # Создаем простой объект для совместимости с BaseStrategy
                class PositionAdapter:
                    def __init__(self, pos_dict):
                        self.entry_price = pos_dict.get('entry_price')
                        self.side = pos_dict.get('side')
                        self.max_price = pos_dict.get('max_price', pos_dict.get('entry_price'))
                        self.min_price = pos_dict.get('min_price', pos_dict.get('entry_price'))

                # Определяем правильную сигнатуру метода calculate_trailing_stop_price
                if hasattr(self.legacy, 'should_update_trailing_stop'):
                    position_adapter = PositionAdapter(pos)
                    should_update = self.legacy.should_update_trailing_stop(position_adapter, current_price)
                    if should_update:
                        # Определяем сигнатуру метода
                        if len(self.legacy.calculate_trailing_stop_price.__code__.co_varnames) == 5:  # self, entry_price, current_price, side, symbol
                            # Сигнатура NovichokStrategy (4 аргумента)
                            trailing_stop_price = self.legacy.calculate_trailing_stop_price(entry_price, current_price, strategy_side, symbol)
                        elif len(self.legacy.calculate_trailing_stop_price.__code__.co_varnames) == 3:  # self, deal, current_price
                            # Сигнатура BaseStrategy (2 аргумента)
                            trailing_stop_price = self.legacy.calculate_trailing_stop_price(position_adapter, current_price)
                        else:
                            trailing_stop_price = None

                        # Если метод вернул None, используем fallback
                        if trailing_stop_price is None:
                            trailing_stop_price = entry_price * (0.98 if strategy_side == 'long' else 1.02)
                    else:
                        # Если обновление не нужно, используем текущий стоп-лосс
                        current_stop_loss = pos.get('stop_loss')
                        if current_stop_loss is not None:
                            trailing_stop_price = current_stop_loss
                        else:
                            # Fallback: рассчитываем стоп-лосс на основе entry_price
                            trailing_stop_price = entry_price * (0.98 if strategy_side == 'long' else 1.02)
                else:
                    # Fallback на старую логику для совместимости
                    try:
                        trailing_stop_price = self.legacy.calculate_trailing_stop_price(entry_price, current_price, strategy_side, symbol)
                    except Exception as e:
                        print(f"⚠️ Ошибка вызова calculate_trailing_stop_price: {e}")
                        trailing_stop_price = entry_price * (0.98 if strategy_side == 'long' else 1.02)
                trailing_stop_triggered = (
                    (pos_side == 'BUY' and current_price <= trailing_stop_price) or
                    (pos_side == 'SELL' and current_price >= trailing_stop_price)
                )

                if trailing_stop_triggered:
                    close_intent = OrderIntent(
                        symbol=symbol,
                        side='SELL' if pos_side == 'BUY' else 'BUY',
                        sizing='close',
                        size=0,
                        role='close'
                    )
                    print(f"📈 NovichokAdapter: ТРЕЙЛИНГ-СТОП! Цена {current_price:.2f} достигла уровня {trailing_stop_price:.2f}")
                    return Decision(intents=[close_intent])

            return Decision(intents=[])
        intent = OrderIntent(
            symbol=symbol,
            side=side,
            sizing="risk_pct",
            size=risk_pct,
            role="primary"
        )
        print(f"✅ NovichokAdapter: Создан intent: {intent.symbol} {intent.side} {intent.role}")
        return Decision(intents=[intent])

