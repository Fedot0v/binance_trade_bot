from __future__ import annotations

from typing import Dict, Any, Optional


class BacktestTradeExecutor:
    """Исполнитель торговых решений для бэктеста.

    - Не делает реальных запросов на биржу
    - Рассчитывает комиссии, спред и проскальзывание
    - Предоставляет те же данные, что и реальный исполнитель ожидает в пайплайне бэктеста
    """

    def __init__(self, fee_rate: float = 0.0004, slippage_bps: float = 0.0, spread_bps: float = 0.0) -> None:
        # fee_rate: комиссия на одну сторону (taker), доля от notional
        # slippage_bps: проскальзывание в б.п. (1 bps = 0.01%)
        # spread_bps: полный спред в б.п.; половина применяется на сторону
        self.fee_rate = fee_rate
        self.slippage_bps = slippage_bps
        self.spread_bps = spread_bps

    def _apply_price_impacts(self, side: str, reference_price: float) -> float:
        """Возвращает эффективную цену с учетом спреда и проскальзывания."""
        half_spread = 0.0  # по умолчанию отключено
        slippage = 0.0     # по умолчанию отключено
        impact = half_spread + slippage
        if side == 'BUY':
            return reference_price * (1.0 + impact)
        return reference_price * (1.0 - impact)

    def can_open_position(self, intent, open_positions: Dict[str, Dict[str, Any]], balance: float) -> bool:
        # Одна позиция на символ
        if intent.symbol in open_positions:
            print(f"⚠️ Позиция {intent.symbol} уже открыта")
            return False

        # Требуемый баланс
        if intent.sizing == "risk_pct":
            required_balance = balance * intent.size
        elif intent.sizing == "usd":
            required_balance = intent.size
        else:
            required_balance = balance * 0.01

        if required_balance > balance:
            print(f"⚠️ Недостаточно средств: нужно ${required_balance:.2f}, доступно ${balance:.2f}")
            return False

        if required_balance < 5:
            print(f"⚠️ Слишком маленькая позиция: ${required_balance:.2f}")
            return False

        return True

    def execute(
        self,
        intent,
        current_price: float,
        current_time,
        balance: float,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Симулирует исполнение ордера по рынку и возвращает trade-словарь."""
        try:
            # Применяем ценовые воздействия
            effective_price = self._apply_price_impacts(intent.side, current_price)

            if intent.sizing == "risk_pct":
                size_usd = balance * intent.size
            elif intent.sizing == "usd":
                size_usd = intent.size
            else:
                size_usd = balance * 0.01

            if size_usd > balance:
                print(f"⚠️ Недостаточно средств для сделки: нужно ${size_usd:.2f}, доступно ${balance:.2f}")
                return None

            quantity = size_usd / effective_price
            open_fee = size_usd * self.fee_rate

            trade = {
                'timestamp': current_time,
                'symbol': symbol,
                'side': intent.side,
                'price': effective_price,
                'quantity': quantity,
                'size': quantity,
                'size_usd': size_usd,
                'balance_before': balance,
                'new_balance': balance - open_fee,
                'pnl': 0.0,
                'status': 'executed',
                'fee_open': open_fee,
            }

            print(f"📊 Backtest trade: {intent.side} {quantity:.6f} {symbol} @ ${effective_price:.2f}")
            return trade
        except Exception as e:
            print(f"❌ Ошибка при симуляции сделки: {e}")
            return None


