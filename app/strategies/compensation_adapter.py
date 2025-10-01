from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

import pandas as pd

from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters
from strategies.contracts import Decision, OrderIntent, MarketData, OpenState, Strategy
from strategies.compensation_strategy import CompensationStrategy
from services.deal_service import DealService
# from strategies.market_data import MarketData


def _sym_str(x) -> str:
    return x.value if hasattr(x, "value") else str(x)


class CompensationAdapter(Strategy):
    """
    Адаптер для стратегии "Компенсация и реакция"
    Управляет входом в BTC и компенсацией через ETH
    """

    id = "compensation-adapter"

    def __init__(self, strategy: CompensationStrategy, template: Any, deal_service: DealService):
        super().__init__(strategy_id="compensation", symbols=strategy.required_symbols(template=template))
        if not isinstance(strategy, CompensationStrategy):
            # print(f"❌ ERROR: Wrong strategy type! Expected CompensationStrategy, got {type(self.strategy)}")
            raise ValueError("CompensationAdapter requires CompensationStrategy")
        self.strategy: CompensationStrategy = strategy
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
        # print(f"🔍 DEBUG: CompensationAdapter.decide() called - VERSION FIXED")
        # print(f"🔍 DEBUG: Available symbols in md: {list(md.keys())}")
        # print(f"🔍 DEBUG: Template name: {getattr(template, 'template_name', 'unknown')}")
        # print(f"🔍 DEBUG: Strategy type: {type(self.strategy).__name__}")
        # print(f"🔍 DEBUG: Strategy name: {getattr(self.strategy, 'name', 'unknown')}")

        verbose = getattr(getattr(self, 'strategy', None), 'verbose', False)

        # Проверяем, что это действительно CompensationStrategy
        if not isinstance(self.strategy, CompensationStrategy):
            # print(f"❌ ERROR: Wrong strategy type! Expected CompensationStrategy, got {type(self.strategy)}")
            return Decision(intents=[])

        """
        Принимает решение о входе в позиции BTC и ETH
        """
        btc_symbol = "BTCUSDT"

        btc_df = md.get(btc_symbol)

        if btc_df is None or btc_df.empty:
            print("[COMP] Пропуск решения: нет данных BTC для анализа")
            return Decision(intents=[])

        # Получаем текущую цену BTC
        current_btc_price = btc_df['close'].iloc[-1]
        current_time = btc_df.index[-1] if hasattr(btc_df.index[-1], 'timestamp') else datetime.now()

        # Получаем ETH данные (в dual orchestrator они гарантированно доступны)
        eth_symbol = "ETHUSDT"
        eth_df = md.get(eth_symbol)
        # print(f"✅ CompensationAdapter: Работаем с данными BTC и ETH")

        # Используем open_state из бэктеста вместо deal_service
        btc_position = None
        eth_position = None

        if open_state:
            def _extract_position(node: Any) -> Optional[Dict[str, Any]]:
                try:
                    if isinstance(node, dict):
                        return node.get('position') or (node if 'entry_price' in node and 'side' in node else None)
                    if hasattr(node, 'position'):
                        pos = getattr(node, 'position')
                        if isinstance(pos, dict):
                            return pos
                    maybe = {
                        'deal_id': getattr(node, 'id', None),
                        'entry_price': getattr(node, 'entry_price', None),
                        'entry_time': getattr(node, 'opened_at', None),
                        'side': getattr(node, 'side', None),
                    }
                    if maybe['entry_price'] is not None and maybe['side'] is not None:
                        return maybe
                except Exception:
                    return None
                return None

            if btc_symbol in open_state:
                btc_position = _extract_position(open_state[btc_symbol])
            if eth_symbol in open_state:
                eth_position = _extract_position(open_state[eth_symbol])

        # КРИТИЧЕСКАЯ ПРОВЕРКА: ETH может существовать только вместе с BTC
        # Если есть ETH позиция без BTC — немедленно закрываем ETH и чистим состояние ETH
        if eth_position and not btc_position:
            print("[COMP] Обнаружена ETH позиция без BTC — создаём emergency_close для ETH и чистим состояние ETH")
            close_eth_intent = OrderIntent(
                symbol="ETHUSDT",
                side="SELL" if eth_position['side'] == "BUY" else "BUY",
                sizing="close",
                size=0,
                role="emergency_close"
            )
            # Чистим состояние ETH, так как BTC отсутствует
            self.strategy.clear_eth_state()
            return Decision(intents=[close_eth_intent])

        # Обновляем состояние стратегии на основе позиций бэктеста
        self._update_strategy_state_from_positions(btc_position, eth_position, current_time)
        # Обновляем флаг had_btc, если в этом прогоне видим реальную BTC позицию
        if btc_position:
            try:
                self.strategy.state.had_btc = True
                # Обновим last_btc_deal_id для привязки компенсации к текущему BTC
                deal_id = btc_position.get('deal_id', 1)
                self.strategy.state.last_btc_deal_id = deal_id
            except Exception:
                pass
        # Если BTC отсутствует, помечаем закрытие ТОЛЬКО если ранее в этом прогоне BTC уже открывался (had_btc)
        if not btc_position and getattr(self.strategy.state, 'had_btc', False):
            self.strategy.mark_btc_closed(current_time)

        # print(f"🔍 DEBUG: Состояние стратегии после обновления:")
        # print(f"   btc_deal_id: {self.strategy.state.btc_deal_id}")
        # print(f"   btc_entry_price: {self.strategy.state.btc_entry_price}")
        # print(f"   btc_side: {self.strategy.state.btc_side}")
        # print(f"   eth_deal_id: {self.strategy.state.eth_deal_id}")
        # print(f"   compensation_triggered: {self.strategy.state.compensation_triggered}")

        intents = []

        # Логика входа в BTC (если нет открытой позиции)
        if not btc_position:
            # print("🔍 DEBUG: Нет BTC позиции, проверяем вход")
            btc_intent = self._generate_btc_entry_intent(btc_df, template)
            if btc_intent:
                print(f"✅ CompensationAdapter: Создан BTC entry intent: {btc_intent.symbol} {btc_intent.side} {btc_intent.role}")
                intents.append(btc_intent)
            else:
                # Подробно логируем причины холда
                try:
                    # Рассчитываем текущие EMA и отклонение для наглядности (без повторного вызова generate_signal)
                    ema_fast = btc_df['close'].ewm(span=self.strategy.ema_fast).mean().iloc[-1]
                    ema_slow = btc_df['close'].ewm(span=self.strategy.ema_slow).mean().iloc[-1]
                    diff_pct = abs(float(ema_fast) - float(ema_slow)) / float(ema_slow) if float(ema_slow) != 0 else 0.0
                    if verbose:
                        print(f"[HOLD] BTC: сигнал=hold | EMA_fast={float(ema_fast):.2f} EMA_slow={float(ema_slow):.2f} diff={diff_pct*100:.2f}% < threshold={self.strategy.trend_threshold*100:.2f}%")
                except Exception as e:
                    if verbose:
                        print(f"[HOLD] BTC: не удалось вычислить детали причины hold: {e}")
                # print("❌ CompensationAdapter: BTC entry intent не создан")
        else:
            # Есть BTC — проверяем, нужна ли компенсация. Открывать ETH можно только один раз за жизнь BTC-позиции
            if not eth_position and not self.strategy.state.compensation_triggered:
                if verbose:
                    print("[COMP] Есть BTC без ETH, проверяем условия компенсации")
                eth_intент = self._generate_eth_compensation_intent(
                    btc_df, current_btc_price, current_time, template, md
                )
                if eth_intент:
                    # Доп. защита: запрещаем второй ETH для того же BTC deal
                    current_deal_id = getattr(self.strategy.state, 'last_btc_deal_id', None)
                    if current_deal_id is not None and getattr(self.strategy.state, 'compensation_done_for_deal_id', None) == current_deal_id:
                        if verbose:
                            print("[COMP] Компенсация для этого BTC уже выполнена — пропускаем повторный ETH")
                    else:
                        self.strategy.state.compensation_done_for_deal_id = current_deal_id
                    print(f"✅ CompensationAdapter: Создан ETH compensation intent: {eth_intент.symbol} {eth_intент.side} {eth_intент.role}")
                    intents.append(eth_intент)
                else:
                    if verbose:
                        print("[COMP] Компенсация не требуется: условия не выполнены")

        # Дополнительно: если BTC закрыт недавно, но ETH ещё не открыт — проверим компенсацию в пост-окне
        # Разрешаем пост-компенсацию только если в этом прогоне уже был реальный вход в BTC (had_btc=True)
        if (
            not btc_position
            and not eth_position
            and not self.strategy.state.compensation_triggered
            and getattr(self.strategy.state, 'had_btc', False)
            and self.strategy.can_compensate_after_close(current_time)
        ):
            if verbose:
                print("[COMP] Пост-компенсация: BTC закрыт недавно, проверяем условия для ETH")
            eth_intent_post = self._generate_eth_compensation_intent(
                btc_df, current_btc_price, current_time, template, md
            )
            if eth_intent_post:
                # Пост-компенсация: также блокируем повторную компенсацию для того же BTC
                last_deal_id = getattr(self.strategy.state, 'last_btc_deal_id', None)
                if last_deal_id is not None and getattr(self.strategy.state, 'compensation_done_for_deal_id', None) == last_deal_id:
                    if verbose:
                        print("[COMP] Пост-компенсация уже выполнена для этого BTC — пропускаем")
                else:
                    self.strategy.state.compensation_done_for_deal_id = last_deal_id
                    print(f"✅ CompensationAdapter: Создан ETH compensation intent (post-close): {eth_intent_post.symbol} {eth_intent_post.side} {eth_intent_post.role}")
                    intents.append(eth_intent_post)
            # else:
            #     print("❌ CompensationAdapter: ETH compensation intent не создан")

        # Логика закрытия позиций
        # print("🔍 DEBUG: Проверяем закрытие позиций")
        close_intents = self._generate_close_intents(btc_df, eth_df, btc_position, eth_position)
        if close_intents:
            if verbose:
                print(f"✅ CompensationAdapter: Созданы close intents: {len(close_intents)}")
            intents.extend(close_intents)
        else:
            if verbose:
                print("[COMP] Close intents не созданы: условия закрытия не выполнены")
        # else:
        #     print("❌ CompensationAdapter: Close intents не созданы")

        # print(f"🔍 DEBUG: CompensationAdapter итого интентов: {len(intents)}")
        # for i, intent in enumerate(intents):
        #     print(f"   Intent {i+1}: {intent.symbol} {intent.side} {intent.role}")
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
                eth_side=eth_position['side'],
                compensation_triggered=True
            )

    def _generate_btc_entry_intent(self, btc_df: pd.DataFrame, template) -> Optional[OrderIntent]:
        """Генерирует намерение входа в BTC по логике новичка"""
        signal = self.strategy.generate_signal(btc_df)

        # print(f"🔍 DEBUG: _generate_btc_entry_intent - signal: {signal}, df_len: {len(btc_df)}")

        if signal == "hold":
            # print("🔍 DEBUG: Signal is 'hold', returning None")
            return None

        side = "BUY" if signal == "long" else "SELL"

        # Используем параметры BTC из стратегии
        btc_risk_pct = self.strategy.btc_risk_pct

        # print(f"🔍 DEBUG: Creating BTC entry intent: {side} {btc_risk_pct}")

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
        current_btc_price: float,
        current_time: datetime,
        template,
        md: Dict[str, pd.DataFrame] # Добавляем md для получения данных ETH
    ) -> Optional[OrderIntent]:
        """Генерирует намерение компенсации через ETH"""

        # print(f"🔍 DEBUG: _generate_eth_compensation_intent called")
        verbose = getattr(getattr(self, 'strategy', None), 'verbose', False)

        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: компенсация возможна только при наличии активной BTC позиции
        # либо в пост-окно после её закрытия (при сохранённых entry_price/side), и если не была уже выполнена
        if self.strategy.state.compensation_triggered:
            if verbose:
                print("[COMP] Компенсация уже была выполнена ранее — повторный вход запрещён")
            return None
        # Требуем наличие цены входа и стороны BTC
        if not getattr(self.strategy.state, 'btc_entry_price', None) or not getattr(self.strategy.state, 'btc_side', None):
            if verbose:
                print("[COMP] Невозможно создать компенсацию: не хватает данных BTC (entry_price/side)")
            return None
        # Разрешаем, если BTC ещё открыт (btc_deal_id есть) ИЛИ если пост-окно после закрытия активно
        btc_active = getattr(self.strategy.state, 'btc_deal_id', None) is not None
        post_window = self.strategy.can_compensate_after_close(current_time)
        if not (btc_active or post_window):
            if verbose:
                print("[COMP] Невозможно создать компенсацию: нет активной BTC позиции и пост-окно истекло")
            return None

        # Получаем данные ETH по запросу
        eth_symbol = "ETHUSDT"
        
        # Получаем полный DataFrame для ETH из md
        full_eth_df = md.get(eth_symbol)
        if full_eth_df is None or full_eth_df.empty:
            if verbose:
                print(f"[COMP] Нет ETH данных в market_data — компенсация недоступна")
            return None
        
        # Берем данные за последние N свечей для анализа тренда ETH
        required_eth_candles = self.strategy.ema_slow + self.strategy.compensation_delay_candles + 10 # Добавляем запас
        
        # Фильтруем данные ETH до текущего времени и берем нужное количество свечей
        eth_df_filtered = full_eth_df[full_eth_df.index <= current_time]
        
        if len(eth_df_filtered) < required_eth_candles:
            if verbose:
                print(f"[COMP] ETH данных недостаточно для компенсации: есть {len(eth_df_filtered)}, нужно {required_eth_candles}")
            return None
        
        # Берем последние required_eth_candles для анализа
        eth_df_for_analysis = eth_df_filtered.iloc[-required_eth_candles:]

        # Проверяем условия для компенсации
        if not self.strategy.should_trigger_compensation(btc_df, eth_df_for_analysis, current_btc_price, current_time):
            if verbose:
                print("[COMP] Условия компенсации не выполнены (should_trigger_compensation=False)")
            return None
            
        # Определяем сторону для ETH (совпадает с BTC). Нормализуем BUY/SELL по входу в BTC
        eth_side = self.strategy.get_eth_side()
        
        # Используем параметры ETH из стратегии
        eth_risk_pct = self.strategy.eth_risk_pct
        
        order_intent = OrderIntent(
            symbol="ETHUSDT",
            side=eth_side,
            sizing="risk_pct",
            size=eth_risk_pct,
            role="compensation"
        )
        # Зафиксируем сторону и признак компенсации в состоянии (для корректного закрытия и запрета повторных входов)
        self.strategy.update_state(eth_side=eth_side, compensation_triggered=True)
        if verbose:
            print(f"[COMP] Компенсация подтверждена: side={eth_side} risk_pct={eth_risk_pct}")
        return order_intent

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
        verbose = getattr(getattr(self, 'strategy', None), 'verbose', False)

        # BTC: не создаём close-интенты — закрытие только по стоп-лоссу на бирже
        if not btc_position:
            # Если пост-окно компенсации ещё активно — НЕ чистим BTC-состояние, чтобы сохранить entry_price/side
            if not self.strategy.can_compensate_after_close(current_time):
                # Окно истекло — можно очищать состояние BTC
                self.strategy.clear_btc_state()
        else:
            # Для бэктеста: разрешаем стратегии инициировать закрытие BTC по своим условиям
            try:
                should_close_btc, btc_reason = self.strategy.should_close_btc_position(btc_df, current_time)
                if should_close_btc:
                    if verbose:
                        print(f"✅ CompensationAdapter: Создаем close интент для BTC: {btc_reason}")
                    intents.append(OrderIntent(
                        symbol="BTCUSDT",
                        side="SELL" if btc_position['side'] == "BUY" else "BUY",
                        sizing="close",
                        size=0,
                        role="close"
                    ))
            except Exception:
                pass

        # Проверяем закрытие ETH
        if eth_position:
            # print(f"🔍 DEBUG: Проверяем закрытие ETH позиции: {eth_position}")
            should_close_eth, eth_reason = self.strategy.should_close_eth_position(eth_df, current_time)
            # print(f"🔍 DEBUG: Результат проверки ETH: close={should_close_eth}, reason='{eth_reason}'")
            # ETH: разрешаем close-интент только для emergency сценариев
            if should_close_eth and isinstance(eth_reason, str) and "emergency_close" in eth_reason:
                if verbose:
                    print(f"✅ CompensationAdapter: Создаем emergency close интент для ETH: {eth_reason}")
                intents.append(OrderIntent(
                    symbol="ETHUSDT",
                    side="SELL" if eth_position['side'] == "BUY" else "BUY",
                    sizing="close",
                    size=0,
                    role="close"
                ))
        else:
            # Нет ETH — очищаем ETH-состояние на всякий случай
            self.strategy.clear_eth_state()

        return intents
