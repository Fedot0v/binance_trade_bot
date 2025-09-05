from typing import Dict, List, Any, Optional
from datetime import datetime

import pandas as pd

from strategies.contracts import Decision, OrderIntent
from strategies.compensation_strategy import CompensationStrategy
from services.deal_service import DealService


def _sym_str(x) -> str:
    return x.value if hasattr(x, "value") else str(x)


class CompensationAdapter:
    """
    Адаптер для стратегии "Компенсация и реакция"
    Управляет входом в BTC и компенсацией через ETH
    """

    id = "compensation-adapter"

    def __init__(self, compensation_strategy: CompensationStrategy, deal_service: DealService):
        self.strategy = compensation_strategy
        self.deal_service = deal_service

    def required_symbols(self, template) -> List[str]:
        """Возвращает список необходимых символов: BTC и ETH для компенсационной стратегии"""
        return ["BTCUSDT", "ETHUSDT"]

    async def decide(
        self,
        md: Dict[str, pd.DataFrame],
        template,
        open_state: Dict[str, Any] | None = None
    ) -> Decision:
        print(f"🔍 DEBUG: CompensationAdapter.decide() called - VERSION FIXED")
        print(f"🔍 DEBUG: Available symbols in md: {list(md.keys())}")
        print(f"🔍 DEBUG: Template name: {getattr(template, 'template_name', 'unknown')}")
        print(f"🔍 DEBUG: Strategy type: {type(self.strategy).__name__}")
        print(f"🔍 DEBUG: Strategy name: {getattr(self.strategy, 'name', 'unknown')}")

        # Проверяем, что это действительно CompensationStrategy
        if not isinstance(self.strategy, CompensationStrategy):
            print(f"❌ ERROR: Wrong strategy type! Expected CompensationStrategy, got {type(self.strategy)}")
            return Decision(intents=[])

        """
        Принимает решение о входе в позиции BTC и ETH
        """
        btc_symbol = "BTCUSDT"

        btc_df = md.get(btc_symbol)

        if btc_df is None or btc_df.empty:
            return Decision(intents=[])

        # Получаем текущую цену BTC
        current_btc_price = btc_df['close'].iloc[-1]
        current_time = btc_df.index[-1] if hasattr(btc_df.index[-1], 'timestamp') else datetime.now()

        # Получаем ETH данные (в dual orchestrator они гарантированно доступны)
        eth_symbol = "ETHUSDT"
        eth_df = md.get(eth_symbol)
        print(f"✅ CompensationAdapter: Работаем с данными BTC и ETH")

        # Используем open_state из бэктеста вместо deal_service
        btc_position = None
        eth_position = None

        if open_state:
            if btc_symbol in open_state:
                btc_position = open_state[btc_symbol].get('position')
            if eth_symbol in open_state:
                eth_position = open_state[eth_symbol].get('position')

        # КРИТИЧЕСКАЯ ПРОВЕРКА: CompensationAdapter НИКОГДА не должен открывать ETH без BTC
        print(f"🔍 DEBUG: Проверка позиций - BTC: {btc_position is not None}, ETH: {eth_position is not None}")

        # Если есть ETH позиция без BTC - это ошибка логики
        if eth_position and not btc_position:
            print("❌ ERROR: ETH позиция существует без BTC! Это нарушение логики компенсационной стратегии")
            # Создаем intent для закрытия ETH позиции
            close_eth_intent = OrderIntent(
                symbol="ETHUSDT",
                side="SELL" if eth_position['side'] == "BUY" else "BUY",
                sizing="close",
                size=0,
                role="emergency_close"
            )
            print(f"🚨 CompensationAdapter: Создан экстренный intent закрытия ETH: {close_eth_intent.symbol} {close_eth_intent.side} {close_eth_intent.role}")
            return Decision(intents=[close_eth_intent])

        # Обновляем состояние стратегии на основе позиций бэктеста
        self._update_strategy_state_from_positions(btc_position, eth_position, current_time)

        print(f"🔍 DEBUG: Состояние стратегии после обновления:")
        print(f"   btc_deal_id: {self.strategy.state.btc_deal_id}")
        print(f"   btc_entry_price: {self.strategy.state.btc_entry_price}")
        print(f"   btc_side: {self.strategy.state.btc_side}")
        print(f"   eth_deal_id: {self.strategy.state.eth_deal_id}")
        print(f"   compensation_triggered: {self.strategy.state.compensation_triggered}")

        intents = []

        # Логика входа в BTC (если нет открытой позиции)
        if not btc_position:
            print("🔍 DEBUG: Нет BTC позиции, проверяем вход")
            btc_intent = self._generate_btc_entry_intent(btc_df, template)
            if btc_intent:
                print(f"✅ CompensationAdapter: Создан BTC entry intent: {btc_intent.symbol} {btc_intent.side} {btc_intent.role}")
                intents.append(btc_intent)
            else:
                print("❌ CompensationAdapter: BTC entry intent не создан")
        else:
            print(f"🔍 DEBUG: BTC позиция уже есть: {btc_position}")

        # Логика компенсации через ETH
        if btc_position and not eth_position:
            print("🔍 DEBUG: Есть BTC позиция, нет ETH - проверяем компенсацию")
            eth_intent = self._generate_eth_compensation_intent(
                btc_df, eth_df, current_btc_price, current_time, template
            )
            if eth_intent:
                print(f"✅ CompensationAdapter: Создан ETH compensation intent: {eth_intent.symbol} {eth_intent.side} {eth_intent.role}")
                intents.append(eth_intent)
            else:
                print("❌ CompensationAdapter: ETH compensation intent не создан")

        # Логика закрытия позиций
        print("🔍 DEBUG: Проверяем закрытие позиций")
        close_intents = self._generate_close_intents(btc_df, eth_df, btc_position, eth_position)
        if close_intents:
            print(f"✅ CompensationAdapter: Созданы close intents: {len(close_intents)}")
            intents.extend(close_intents)
        else:
            print("❌ CompensationAdapter: Close intents не созданы")

        print(f"🔍 DEBUG: CompensationAdapter итого интентов: {len(intents)}")
        for i, intent in enumerate(intents):
            print(f"   Intent {i+1}: {intent.symbol} {intent.side} {intent.role}")
        return Decision(intents=intents)

    async def _get_open_deals(self, user_id, bot_id) -> List:
        """Получает открытые сделки пользователя"""
        try:
            if self.deal_service and hasattr(self.deal_service, 'get_open_deals') and user_id and bot_id:
                return await self.deal_service.get_open_deals(user_id, bot_id)
            else:
                # Для бэктеста - просто возвращаем пустой список
                return []
        except Exception as e:
            print(f"Ошибка при получении открытых сделок: {e}")
            return []

    def _update_strategy_state(self, btc_deal, eth_deal):
        """Обновляет состояние стратегии на основе открытых сделок"""
        if btc_deal:
            self.strategy.update_state(
                btc_deal_id=btc_deal.id,
                btc_entry_price=btc_deal.entry_price,
                btc_entry_time=btc_deal.opened_at,
                btc_side=btc_deal.side
            )
        if eth_deal:
            self.strategy.update_state(
                eth_deal_id=eth_deal.id,
                compensation_triggered=True
            )

    def _update_strategy_state_from_positions(self, btc_position, eth_position, current_time):
        """Обновляет состояние стратегии на основе позиций бэктеста"""
        if btc_position:
            self.strategy.update_state(
                btc_deal_id=btc_position.get('deal_id', 1),
                btc_entry_price=btc_position['entry_price'],
                btc_entry_time=btc_position['entry_time'],
                btc_side=btc_position['side']
            )
        if eth_position:
            self.strategy.update_state(
                eth_deal_id=eth_position.get('deal_id', 2),
                eth_entry_price=eth_position['entry_price'],
                eth_entry_time=eth_position['entry_time'],
                compensation_triggered=True
            )

    def _generate_btc_entry_intent(self, btc_df: pd.DataFrame, template) -> Optional[OrderIntent]:
        """Генерирует намерение входа в BTC по логике новичка"""
        signal = self.strategy.generate_signal(btc_df)

        print(f"🔍 DEBUG: _generate_btc_entry_intent - signal: {signal}, df_len: {len(btc_df)}")

        if signal == "hold":
            print("🔍 DEBUG: Signal is 'hold', returning None")
            return None

        side = "BUY" if signal == "long" else "SELL"

        # Используем параметры BTC из стратегии
        btc_risk_pct = self.strategy.btc_risk_pct

        print(f"🔍 DEBUG: Creating BTC entry intent: {side} {btc_risk_pct}")

        return OrderIntent(
            symbol="BTCUSDT",
            side=side,
            sizing="risk_pct",
            size=btc_risk_pct,
            role="primary"
        )

    def _generate_eth_compensation_intent(
        self,
        btc_df: pd.DataFrame,
        eth_df: pd.DataFrame,
        current_btc_price: float,
        current_time: datetime,
        template
    ) -> Optional[OrderIntent]:
        """Генерирует намерение компенсации через ETH"""

        print(f"🔍 DEBUG: _generate_eth_compensation_intent called")

        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: компенсация возможна только при наличии BTC позиции
        if not self.strategy.state.btc_deal_id or not self.strategy.state.btc_entry_price:
            print("❌ ERROR: Попытка создать ETH компенсацию без BTC позиции!")
            return None

        # Проверяем условия для компенсации
        if not self.strategy.should_trigger_compensation(btc_df, current_btc_price, current_time):
            print("❌ Compensation conditions not met")
            return None
            
        # Определяем сторону для ETH (противоположную BTC)
        eth_side = self.strategy.get_eth_side()
        
        # Используем параметры ETH из стратегии
        eth_risk_pct = self.strategy.eth_risk_pct
        
        return OrderIntent(
            symbol="ETHUSDT",
            side=eth_side,
            sizing="risk_pct",
            size=eth_risk_pct,
            role="compensation"
        )

    def _generate_close_intents(
        self,
        btc_df: pd.DataFrame,
        eth_df: pd.DataFrame = None,
        btc_position = None,
        eth_position = None
    ) -> List[OrderIntent]:
        """Генерирует намерения закрытия позиций"""
        intents = []
        current_time = btc_df.index[-1] if hasattr(btc_df.index[-1], 'timestamp') else datetime.now()

        # Проверяем закрытие BTC
        if btc_position:
            print(f"🔍 DEBUG: Проверяем закрытие BTC позиции: {btc_position}")
            should_close_btc, btc_reason = self.strategy.should_close_btc_position(btc_df, current_time)
            print(f"🔍 DEBUG: Результат проверки BTC: close={should_close_btc}, reason='{btc_reason}'")
            if should_close_btc:
                print(f"✅ Создаем интент закрытия BTC: {btc_reason}")
                intents.append(OrderIntent(
                    symbol="BTCUSDT",
                    side="SELL" if btc_position['side'] == "BUY" else "BUY",
                    sizing="close",
                    size=0,
                    role="close"
                ))

        # Проверяем закрытие ETH
        if eth_position:
            print(f"🔍 DEBUG: Проверяем закрытие ETH позиции: {eth_position}")
            should_close_eth, eth_reason = self.strategy.should_close_eth_position(eth_df, current_time)
            print(f"🔍 DEBUG: Результат проверки ETH: close={should_close_eth}, reason='{eth_reason}'")
            if should_close_eth:
                print(f"✅ CompensationAdapter: Создаем интент закрытия ETH: {eth_reason}")
                intents.append(OrderIntent(
                    symbol="ETHUSDT",
                    side="SELL" if eth_position['side'] == "BUY" else "BUY",
                    sizing="close",
                    size=0,
                    role="close"
                ))

        return intents
