import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from strategies.base_strategy import BaseStrategy
from services.strategy_parameters import StrategyParameters
from strategies.contracts import Decision, OrderIntent
from schemas.user_strategy_template import UserStrategyTemplateRead


@dataclass
class CompensationState:
    """Состояние стратегии компенсации"""
    btc_deal_id: Optional[int] = None
    eth_deal_id: Optional[int] = None
    btc_entry_price: Optional[float] = None
    btc_entry_time: Optional[datetime] = None
    btc_side: Optional[str] = None
    eth_entry_price: Optional[float] = None  # Цена входа в ETH компенсацию
    eth_entry_time: Optional[datetime] = None  # Время входа в ETH компенсацию
    btc_position: Optional[Dict] = None  # Позиция BTC
    eth_position: Optional[Dict] = None  # Позиция ETH
    compensation_triggered: bool = False
    compensation_time: Optional[datetime] = None
    compensation_signal_time: Optional[datetime] = None  # Время первого сигнала компенсации
    last_btc_price: Optional[float] = None
    btc_candles_against: int = 0
    btc_impulse_detected: bool = False
    partial_close_done: bool = False  # Флаг частичного закрытия BTC
    
    def reset_state(self) -> None:
        """Сбрасывает состояние стратегии"""
        self.state.btc_deal_id = None
        self.state.eth_deal_id = None
        self.state.btc_entry_price = None
        self.state.btc_entry_time = None
        self.state.btc_side = None
        self.state.eth_entry_price = None
        self.state.eth_entry_time = None
        self.state.btc_position = None
        self.state.eth_position = None
        self.state.compensation_triggered = False
        self.state.compensation_time = None
        self.state.compensation_signal_time = None
        self.state.last_btc_price = None
        self.state.btc_candles_against = 0
        self.state.btc_impulse_detected = False
        self.state.partial_close_done = False


class CompensationStrategy(BaseStrategy):
    """
    УМНАЯ стратегия "Компенсация и реакция"
    
    Основной актив: BTC; страховка: ETH
    Вход в BTC по логике новичка, умная компенсация через ETH при движении против позиции
    """
    
    def __init__(self, params: StrategyParameters):
        self.params = params
        
        # Параметры для BTC (логика новичка)
        self.ema_fast = self.params.get_int("ema_fast", 10)
        self.ema_slow = self.params.get_int("ema_slow", 30)
        self.trend_threshold = self.params.get_float("trend_threshold", 0.001)
        self.btc_risk_pct = self.params.get_float("btc_deposit_prct", 0.05)
        self.btc_stop_loss_pct = self.params.get_float("btc_stop_loss_pct", 0.012)
        self.btc_take_profit_pct = self.params.get_float("btc_take_profit_pct", 0.03)
        self.btc_leverage = self.params.get_int("btc_leverage", 10)
        
        # Параметры для ETH (компенсация)
        self.eth_risk_pct = self.params.get_float("eth_deposit_prct", 0.1)
        self.eth_stop_loss_pct = self.params.get_float("eth_stop_loss_pct", 0.01)
        self.eth_take_profit_pct = self.params.get_float("eth_take_profit_pct", 0.015)
        self.eth_leverage = self.params.get_int("eth_leverage", 10)
        
        # Параметры компенсации
        self.compensation_threshold = self.params.get_float("compensation_threshold", 0.005)  # 0.5%
        self.compensation_delay_candles = self.params.get_int("compensation_delay_candles", 3)  # Задержка перед компенсацией
        self.impulse_threshold = self.params.get_float("impulse_threshold", 0.004)  # 0.4%
        self.candles_against_threshold = self.params.get_int("candles_against_threshold", 2)

        self.trailing_stop_pct = self.params.get_float("trailing_stop_pct", 0.003)  # 0.3%

        # Отладочная информация о параметрах
        print("🎛️ Параметры компенсационной стратегии:")
        print(f"   BTC Stop Loss: {self.btc_stop_loss_pct:.4f} ({self.btc_stop_loss_pct*100:.2f}%)")
        print(f"   BTC Take Profit: {self.btc_take_profit_pct:.4f} ({self.btc_take_profit_pct*100:.2f}%)")
        print(f"   BTC Risk %: {self.btc_risk_pct:.4f} ({self.btc_risk_pct*100:.2f}%)")
        print(f"   ETH Stop Loss: {self.eth_stop_loss_pct:.4f} ({self.eth_stop_loss_pct*100:.2f}%)")
        print(f"   ETH Take Profit: {self.eth_take_profit_pct:.4f} ({self.eth_take_profit_pct*100:.2f}%)")
        print(f"   Compensation Threshold: {self.compensation_threshold:.4f} ({self.compensation_threshold*100:.2f}%)")

        # Состояние стратегии
        self.state = CompensationState()

    def generate_signal(self, df: pd.DataFrame) -> str:
        """Генерирует сигнал для BTC по логике новичка"""
        if len(df) < self.ema_slow:
            return 'hold'

        ema_fast = df['close'].ewm(span=self.ema_fast).mean()
        ema_slow = df['close'].ewm(span=self.ema_slow).mean()

        diff = abs(ema_fast.iloc[-1] - ema_slow.iloc[-1]) / ema_slow.iloc[-1]
        if diff < self.trend_threshold:
            return 'hold'

        return 'long' if ema_fast.iloc[-1] > ema_slow.iloc[-1] else 'short'

    def calculate_position_size(self, balance: float, symbol: str = "BTC") -> float:
        """Рассчитывает размер позиции для BTC или ETH"""
        if symbol == "BTC":
            return balance * self.btc_risk_pct
        else:  # ETH
            return balance * self.eth_risk_pct
    
    def calculate_stop_loss_price(self, entry_price: float, side: str, symbol: str = "BTC") -> float:
        """Рассчитывает цену стоп-лосса для BTC или ETH"""
        if symbol == "BTC":
            stop_loss_pct = self.btc_stop_loss_pct
        else:  # ETH
            stop_loss_pct = self.eth_stop_loss_pct
            
        if side == "BUY":
            return entry_price * (1 - stop_loss_pct)
        else:  # SELL
            return entry_price * (1 + stop_loss_pct)

    def calculate_take_profit_price(self, entry_price: float, side: str, symbol: str = "BTC") -> float:
        """Рассчитывает цену тейк-профита для BTC или ETH"""
        if symbol == "BTC":
            take_profit_pct = self.btc_take_profit_pct
        else:  # ETH
            take_profit_pct = self.eth_take_profit_pct
            
        if side == "BUY":
            return entry_price * (1 + take_profit_pct)
        else:  # SELL
            return entry_price * (1 - take_profit_pct)

    def should_trigger_compensation(self, btc_df: pd.DataFrame, current_price: float, current_time: datetime) -> bool:
        """
        УМНАЯ проверка компенсации с адаптивными порогами и улучшенной фильтрацией
        """
        if not self.state.btc_entry_price:
            return False

        if self.state.btc_deal_id is None:
            return False

        # Отладочная информация о проверке компенсации
        price_change_pct = abs(current_price - self.state.btc_entry_price) / self.state.btc_entry_price
        print(f"🔄 Проверка компенсации BTC:")
        print(f"   Текущая цена: ${current_price:.2f}")
        print(f"   Цена входа: ${self.state.btc_entry_price:.2f}")
        print(f"   Изменение: {price_change_pct*100:.2f}%")
        print(f"   Порог компенсации: {self.compensation_threshold*100:.2f}%")
        print(f"   BTC сторона: {self.state.btc_side}")
            

        
        # Рассчитываем движение против позиции
        price_change_pct = abs(current_price - self.state.btc_entry_price) / self.state.btc_entry_price
        
        # УПРОЩЕННЫЙ ПОРОГ: используем фиксированный порог для более частых компенсаций
        print(f"   Порог компенсации: {self.compensation_threshold*100:.2f}%")
        if price_change_pct < self.compensation_threshold:
            print(f"   ❌ Изменение {price_change_pct*100:.2f}% меньше порога {self.compensation_threshold*100:.2f}%")
            return False
            
        # Проверяем направление движения
        if self.state.btc_side == "BUY" and current_price < self.state.btc_entry_price:
            movement_against = True
            print("   ✅ BUY позиция движется против (цена ниже входа)")
        elif self.state.btc_side == "SELL" and current_price > self.state.btc_entry_price:
            movement_against = True
            print("   ✅ SELL позиция движется против (цена выше входа)")
        else:
            movement_against = False
            print(f"   ❌ Движение НЕ против позиции (BTC {self.state.btc_side}, цена {'ниже' if current_price < self.state.btc_entry_price else 'выше'} входа)")

        if not movement_against:
            return False
        
        # Если первый раз обнаружили сигнал, запоминаем время
        if self.state.compensation_signal_time is None:
            self.state.compensation_signal_time = current_time
            return False  # Не открываем сразу, ждем
            
        # Проверяем, прошло ли достаточно времени (задержка в свечах)
        time_since_signal = current_time - self.state.compensation_signal_time
        candles_passed = time_since_signal.total_seconds() / 60  # 1 минутные свечи
        
        if candles_passed < self.compensation_delay_candles:
            return False  # Еще не время
            
        # Проверяем свечи против позиции
        self._update_candles_analysis(btc_df)
        
        # Проверяем импульс
        self._check_impulse(btc_df)
        
        # Компенсация если есть 2 свечи против или импульс >0.4%
        return (self.state.btc_candles_against >= self.candles_against_threshold or 
                self.state.btc_impulse_detected)

    def get_compensation_quality_score(self, btc_df: pd.DataFrame, eth_df: pd.DataFrame) -> Dict[str, float]:
        """
        Оценивает качество сигнала компенсации
        Возвращает словарь с метриками качества
        """
        if len(btc_df) < 20 or len(eth_df) < 20:
            return {"volume_ok": False, "correlation_ok": False, "eth_direction_ok": False, "score": 0.0}
        
        # ПРОВЕРКА СИНХРОНИЗАЦИИ: убеждаемся что BTC и ETH в одном временном диапазоне
        btc_last_time = btc_df.index[-1]  # timestamp теперь индекс
        eth_last_time = eth_df.index[-1]  # timestamp теперь индекс
        
        # Разница во времени не должна превышать 1 минуту
        time_diff = abs((btc_last_time - eth_last_time).total_seconds())
        if time_diff > 60:
            print(f"⚠️ ВНИМАНИЕ: Разница во времени BTC/ETH: {time_diff:.0f} сек")
            return {"volume_ok": False, "correlation_ok": False, "eth_direction_ok": False, "score": 0.0}
        
        # ПРАВИЛЬНЫЙ АНАЛИЗ: берем объемы и корреляцию в том же временном диапазоне
        btc_current_time = btc_df.index[-1]  # timestamp теперь индекс
        
        # Ищем индекс ETH свечи с ближайшим временем к текущему BTC
        eth_time_diff = abs(eth_df.index - btc_current_time)
        eth_current_idx = eth_time_diff.argmin()
        
        # Объем BTC (последние 5 и 20 свечей)
        btc_volume_ratio = btc_df['volume'].iloc[-5:].mean() / btc_df['volume'].iloc[-20:].mean()
        
        # Объем ETH в том же временном диапазоне
        if eth_current_idx >= 19:  # Есть минимум 20 свечей назад
            eth_volume_ratio = eth_df['volume'].iloc[eth_current_idx-4:eth_current_idx+1].mean() / eth_df['volume'].iloc[eth_current_idx-19:eth_current_idx+1].mean()
        else:
            eth_volume_ratio = 1.0  # По умолчанию если недостаточно данных
        
        # Корреляция BTC/ETH за последние 10 свечей в том же времени
        if len(btc_df) >= 10 and eth_current_idx >= 9:
            btc_prices = btc_df['close'].iloc[-10:].values
            eth_prices = eth_df['close'].iloc[eth_current_idx-9:eth_current_idx+1].values
            correlation = pd.Series(btc_prices).corr(pd.Series(eth_prices))
        else:
            correlation = 0.8  # По умолчанию
        
        # УЛУЧШЕНИЕ: Проверяем устойчивое направление движения ETH (СТРОГИЕ требования)
        eth_direction_ok = False
        if len(eth_df) >= 5:  # Нужно минимум 5 свечей для анализа
            eth_side = self.get_eth_side()
            
            # ПРОВЕРКА СИНХРОНИЗАЦИИ СВЕЧЕЙ: убеждаемся что анализируем правильные свечи
            btc_current_time = btc_df.index[-1]  # timestamp теперь индекс
            eth_current_time = eth_df.index[-1]  # timestamp теперь индекс
            
            # Если ETH отстает более чем на 2 минуты - не анализируем
            if abs((btc_current_time - eth_current_time).total_seconds()) > 120:
                print(f"⚠️ ETH отстает от BTC на {(btc_current_time - eth_current_time).total_seconds():.0f} сек")
                return {
                    "volume_ok": volume_ok,
                    "correlation_ok": correlation_ok,
                    "eth_direction_ok": False,
                    "btc_volume_ratio": btc_volume_ratio,
                    "eth_volume_ratio": eth_volume_ratio,
                    "correlation": correlation,
                    "score": 0.0
                }
            
            # ПРАВИЛЬНЫЙ АНАЛИЗ: берем ETH свечи в том же временном диапазоне что и BTC
            btc_current_time = btc_df.index[-1]  # timestamp теперь индекс
            
            # Ищем индекс ETH свечи с ближайшим временем к текущему BTC
            eth_time_diff = abs(eth_df.index - btc_current_time)
            eth_current_idx = eth_time_diff.argmin()
            
            # Берем 5 свечей ETH начиная с текущего времени (как у BTC)
            if eth_current_idx >= 4:  # Есть минимум 5 свечей назад
                eth_prices = eth_df['close'].iloc[eth_current_idx-4:eth_current_idx+1].values
                eth_volumes = eth_df['volume'].iloc[eth_current_idx-2:eth_current_idx+1].values
                print(f"📊 ETH анализ: свечи {eth_current_idx-4} до {eth_current_idx} (время BTC: {btc_current_time})")
            else:
                # Если недостаточно свечей - берем последние доступные
                eth_prices = eth_df['close'].iloc[:eth_current_idx+1].values
                eth_volumes = eth_df['volume'].iloc[:eth_current_idx+1].values
                print(f"⚠️ ETH анализ: недостаточно свечей, используем {len(eth_prices)} доступных")
            
            if eth_side == "BUY":
                # Для лонга: проверяем, что ETH растет (СНИЖЕНЫ требования)
                price_trend = eth_prices[4] > eth_prices[0]  # Простой рост
                volume_confirmation = eth_volumes[2] > eth_volumes[0] * 0.5  # Снижены требования к объему
                if price_trend and volume_confirmation:
                    eth_direction_ok = True
            elif eth_side == "SELL":
                # Для шорта: проверяем, что ETH падает (СНИЖЕНЫ требования)
                price_trend = eth_prices[4] < eth_prices[0]  # Простое падение
                volume_confirmation = eth_volumes[2] > eth_volumes[0] * 0.5  # Снижены требования к объему
                if price_trend and volume_confirmation:
                    eth_direction_ok = True
        
        # Оценка качества (СНИЖЕНЫ требования для более частых компенсаций)
        volume_ok = btc_volume_ratio > 0.5 and eth_volume_ratio > 0.5  # Снижены требования к объему
        correlation_ok = correlation > 0.2  # Снижены требования к корреляции
        
        # Общий скор качества (0-100) - ОБЯЗАТЕЛЬНОЕ направление ETH
        quality_score = 0.0
        if volume_ok:
            quality_score += 25
        if correlation_ok:
            quality_score += 25
        if eth_direction_ok:
            quality_score += 50  # УВЕЛИЧЕН вес направления ETH (обязательно!)
        if btc_volume_ratio > 1.2:
            quality_score += 10
        if eth_volume_ratio > 1.2:
            quality_score += 10
        
        return {
            "volume_ok": volume_ok,
            "correlation_ok": correlation_ok,
            "eth_direction_ok": eth_direction_ok,
            "btc_volume_ratio": btc_volume_ratio,
            "eth_volume_ratio": eth_volume_ratio,
            "correlation": correlation,
            "score": quality_score
        }

    def get_compensation_size_multiplier(self, price_change_pct: float) -> float:
        """
        УМНАЯ КОМПЕНСАЦИЯ: возвращает множитель размера ETH в зависимости от силы движения
        (Сделано более консервативным для уменьшения убытков)
        """
        if price_change_pct > 0.005:  # 0.5% - сильное движение против
            return 1.2  # Увеличиваем размер ETH на 20% (было 50%)
        elif price_change_pct > 0.003:  # 0.3% - среднее движение
            return 1.1  # Увеличиваем размер ETH на 10% (было 20%)
        else:
            return 0.8  # Уменьшаем размер на 20% (было 100%)

    def should_partial_close_btc(self, btc_pnl: float, eth_pnl: float) -> bool:
        """
        Проверяет, нужно ли частично закрыть BTC при успешной компенсации
        """
        # Если ETH компенсирует убыток BTC более чем на 50%
        return eth_pnl > 0 and abs(eth_pnl) > abs(btc_pnl) * 0.5

    def should_close_both_positions(self, btc_pnl: float, eth_pnl: float) -> bool:
        """
        ЗАЩИТА ОТ ДВОЙНОГО УБЫТКА: закрывает обе позиции если обе в убытке
        """
        # Если обе позиции в убытке - закрываем обе для минимизации потерь
        return btc_pnl < 0 and eth_pnl < 0

    def create_compensation_position(self, current_eth_price: float, current_time: datetime, 
                                   price_change_pct: float, balance: float) -> Dict:
        """
        Создает позицию компенсации ETH с умными параметрами
        """
        eth_side = self.get_eth_side()
        size_multiplier = self.get_compensation_size_multiplier(price_change_pct)
        
        position = {
            'entry_time': current_time,
            'entry_price': current_eth_price,
            'side': eth_side,
            'size': balance * self.eth_risk_pct * size_multiplier,
            'leverage': self.eth_leverage,
            'stop_loss': self.calculate_stop_loss_price(current_eth_price, eth_side, 'ETH'),
            'take_profit': self.calculate_take_profit_price(current_eth_price, eth_side, 'ETH'),
            'trailing_stop': self.calculate_stop_loss_price(current_eth_price, eth_side, 'ETH'),
            'size_multiplier': size_multiplier
        }
        
        return position

    def update_trailing_stop(self, position: Dict, current_price: float) -> float:
        """Обновляет trailing stop для позиции"""
        if position['side'] == 'BUY':
            # Для лонга: trailing stop двигается вверх за ценой
            new_stop = current_price * (1 - self.trailing_stop_pct)
            return max(position.get('trailing_stop', position['stop_loss']), new_stop)
        else:  # SELL
            # Для шорта: trailing stop двигается вниз за ценой
            new_stop = current_price * (1 + self.trailing_stop_pct)
            return min(position.get('trailing_stop', position['stop_loss']), new_stop)

    def _update_candles_analysis(self, df: pd.DataFrame) -> None:
        """Анализирует свечи против позиции"""
        if len(df) < 3 or not self.state.btc_side:
            return
            
        candles_against = 0
        for i in range(len(df) - 2, len(df)):
            candle = df.iloc[i]
            prev_candle = df.iloc[i-1] if i > 0 else candle
            
            # Определяем направление свечи
            if candle['close'] > candle['open']:  # Зеленая свеча
                candle_direction = "up"
            else:  # Красная свеча
                candle_direction = "down"
                
            # Проверяем, идет ли свеча против позиции
            if self.state.btc_side == "BUY" and candle_direction == "down":
                candles_against += 1
            elif self.state.btc_side == "SELL" and candle_direction == "up":
                candles_against += 1
                
        self.state.btc_candles_against = candles_against

    def _check_impulse(self, df: pd.DataFrame) -> None:
        """Проверяет наличие импульса >0.4%"""
        if len(df) < 2 or not self.state.btc_side:
            return
            
        current_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]
        
        # Рассчитываем изменение цены в процентах
        price_change_pct = abs(current_candle['close'] - prev_candle['close']) / prev_candle['close']
        
        # Проверяем направление импульса
        if self.state.btc_side == "BUY" and current_candle['close'] < prev_candle['close']:
            # Импульс вниз против лонга
            if price_change_pct > self.impulse_threshold:
                self.state.btc_impulse_detected = True
        elif self.state.btc_side == "SELL" and current_candle['close'] > prev_candle['close']:
            # Импульс вверх против шорта
            if price_change_pct > self.impulse_threshold:
                self.state.btc_impulse_detected = True

    def should_close_btc_position(self, btc_df: pd.DataFrame, current_time: datetime) -> Tuple[bool, str]:
        """
        Проверяет, нужно ли закрыть позицию BTC (ВСЕ УСЛОВИЯ ЗАКРЫТИЯ)
        Возвращает (нужно_закрыть, причина)
        """
        print(f"🔍 Вызван should_close_btc_position: deal_id={self.state.btc_deal_id}, entry_price={self.state.btc_entry_price}")

        if not self.state.btc_entry_price:
            print("❌ Нет данных о позиции BTC (нет цены входа)")
            return False, ""

        if self.state.btc_deal_id is None:
            print("❌ Нет данных о позиции BTC (deal_id is None)")
            return False, ""

        current_btc_price = btc_df['close'].iloc[-1]

        # Создаем временный объект позиции из данных состояния
        btc_position = {
            'side': self.state.btc_side,
            'take_profit': self.calculate_take_profit_price(self.state.btc_entry_price, self.state.btc_side, 'BTC'),
            'stop_loss': self.calculate_stop_loss_price(self.state.btc_entry_price, self.state.btc_side, 'BTC'),
            'trailing_stop': self.calculate_stop_loss_price(self.state.btc_entry_price, self.state.btc_side, 'BTC'),
            'entry_time': self.state.btc_entry_time
        }

        # Отладочная информация о проверке закрытия
        print(f"🔍 Проверка закрытия BTC позиции:")
        print(f"   Текущая цена BTC: ${current_btc_price:.2f}")
        print(f"   Цена входа: ${self.state.btc_entry_price:.2f}")
        print(f"   Сторона: {btc_position['side']}")
        print(f"   Take Profit: ${btc_position['take_profit']:.2f}")
        print(f"   Stop Loss: ${btc_position['stop_loss']:.2f}")
        print(f"   Изменение цены: {(current_btc_price - self.state.btc_entry_price) / self.state.btc_entry_price * 100:.2f}%")
        
        # Проверяем тейк-профит
        if (btc_position['side'] == 'BUY' and current_btc_price >= btc_position['take_profit']) or \
           (btc_position['side'] == 'SELL' and current_btc_price <= btc_position['take_profit']):
            print(f"🎯 ТЕЙК-ПРОФИТ! Цена {current_btc_price} {'выше' if btc_position['side'] == 'BUY' else 'ниже'} уровня {btc_position['take_profit']}")
            return True, "take_profit"
        
        # Проверяем trailing stop
        if (btc_position['side'] == 'BUY' and current_btc_price <= btc_position['trailing_stop']) or \
           (btc_position['side'] == 'SELL' and current_btc_price >= btc_position['trailing_stop']):
            return True, "trailing_stop"
        
        # Проверяем стоп-лосс
        if (btc_position['side'] == 'BUY' and current_btc_price <= btc_position['stop_loss']) or \
           (btc_position['side'] == 'SELL' and current_btc_price >= btc_position['stop_loss']):
            print(f"🛑 СТОП-ЛОСС! Цена {current_btc_price} {'ниже' if btc_position['side'] == 'BUY' else 'выше'} уровня {btc_position['stop_loss']}")
            return True, "stop_loss"
        
        # Трейлинг-стоп для BTC
        if self.state.btc_entry_price and self.state.btc_entry_time:
            # Для компенсационной стратегии используем простой trailing stop от текущей цены
            if self.state.btc_side == 'BUY':
                trailing_stop = current_btc_price * (1 - self.trailing_stop_pct)
            else:
                trailing_stop = current_btc_price * (1 + self.trailing_stop_pct)
            if (btc_position['side'] == 'BUY' and current_btc_price <= trailing_stop) or \
               (btc_position['side'] == 'SELL' and current_btc_price >= trailing_stop):
                print(f"📈 ТРЕЙЛИНГ-СТОП BTC! Цена {current_btc_price:.2f} достигла уровня {trailing_stop:.2f}")
                return True, "trailing_stop"
                
        return False, ""

    def should_close_eth_position(self, eth_df: pd.DataFrame, current_time: datetime) -> Tuple[bool, str]:
        """
        Проверяет, нужно ли закрыть позицию ETH (ВСЕ УСЛОВИЯ ЗАКРЫТИЯ)
        Возвращает (нужно_закрыть, причина)
        """
        if self.state.eth_deal_id is None:
            return False, ""

        current_eth_price = eth_df['close'].iloc[-1]

        # Определяем сторону ETH (противоположная BTC)
        eth_side = self.get_eth_side()

        # ИСПОЛЬЗУЕМ ПРАВИЛЬНУЮ ЛОГИКУ: рассчитываем уровни на основе ЦЕНЫ ВХОДА в ETH позицию
        # Для бэктеста цена входа хранится в состоянии, для реальной торговли - берем из позиции
        if hasattr(self.state, 'eth_entry_price') and self.state.eth_entry_price:
            eth_entry_price = self.state.eth_entry_price
        else:
            # Для бэктеста используем цену открытия компенсации
            eth_entry_price = current_eth_price  # Примерная цена входа

        # Рассчитываем правильные уровни на основе цены входа
        take_profit_price = self.calculate_take_profit_price(eth_entry_price, eth_side, 'ETH')
        stop_loss_price = self.calculate_stop_loss_price(eth_entry_price, eth_side, 'ETH')

        print(f"🔍 DEBUG: ETH Close Check | Side: {eth_side} | Entry: {eth_entry_price:.2f} | Current: {current_eth_price:.2f}")
        print(f"🔍 DEBUG: ETH Levels | TP: {take_profit_price:.2f} | SL: {stop_loss_price:.2f}")

        if (eth_side == 'BUY' and current_eth_price >= take_profit_price) or \
           (eth_side == 'SELL' and current_eth_price <= take_profit_price):
            print(f"🎯 ETH TAKE-PROFIT! Цена {current_eth_price:.2f} достигла уровня {take_profit_price:.2f}")
            return True, "take_profit"

        if (eth_side == 'BUY' and current_eth_price <= stop_loss_price) or \
           (eth_side == 'SELL' and current_eth_price >= stop_loss_price):
            print(f"🛑 ETH STOP-LOSS! Цена {current_eth_price:.2f} достигла уровня {stop_loss_price:.2f}")
            return True, "stop_loss"

        if eth_side == 'BUY':
            trailing_stop = current_eth_price * (1 - self.trailing_stop_pct)
        else:
            trailing_stop = current_eth_price * (1 + self.trailing_stop_pct)

        if (eth_side == 'BUY' and current_eth_price <= trailing_stop) or \
           (eth_side == 'SELL' and current_eth_price >= trailing_stop):
            print(f"📈 ETH TRAILING-STOP! Цена {current_eth_price:.2f} достигла уровня {trailing_stop:.2f}")
            return True, "trailing_stop"

        if self.state.eth_entry_time:
            emergency_close, emergency_reason = self.should_emergency_close_eth(0, self.state.eth_entry_time, current_time)
            if emergency_close:
                print(f"🚨 ETH EMERGENCY CLOSE! {emergency_reason}")
                return True, emergency_reason

        return False, ""



    def get_eth_side(self) -> str:
        """Возвращает сторону для ETH (КОМПЕНСАЦИЯ - в противоположном направлении от BTC)"""
        if self.state.btc_side == "BUY":
            return "SELL"
        else:
            return "BUY"


    def update_state(self, btc_deal_id: Optional[int] = None,
                    eth_deal_id: Optional[int] = None,
                    btc_entry_price: Optional[float] = None,
                    btc_entry_time: Optional[datetime] = None,
                    btc_side: Optional[str] = None,
                    eth_entry_price: Optional[float] = None,
                    eth_entry_time: Optional[datetime] = None,
                    compensation_triggered: bool = False) -> None:
        """Обновляет состояние стратегии"""
        if btc_deal_id is not None:
            self.state.btc_deal_id = btc_deal_id
        if eth_deal_id is not None:
            self.state.eth_deal_id = eth_deal_id
        if btc_entry_price is not None:
            self.state.btc_entry_price = btc_entry_price
        if btc_entry_time is not None:
            self.state.btc_entry_time = btc_entry_time
        if btc_side is not None:
            self.state.btc_side = btc_side
        if eth_entry_price is not None:
            self.state.eth_entry_price = eth_entry_price
        if eth_entry_time is not None:
            self.state.eth_entry_time = eth_entry_time
        if compensation_triggered:
            self.state.compensation_triggered = True
            self.state.compensation_time = datetime.now()

    def reset_state(self) -> None:
        """Сбрасывает состояние стратегии"""
        self.state = CompensationState()

    def should_close_both_positions(self, btc_pnl: float, eth_pnl: float) -> bool:
        """
        ЗАЩИТА ОТ ДВОЙНОГО УБЫТКА: закрывает обе позиции если обе в убытке
        """

        return btc_pnl < 0 and eth_pnl < 0

    def should_emergency_close_eth(self, eth_pnl: float, eth_entry_time: datetime, current_time: datetime) -> Tuple[bool, str]:
        """
        ЭКСТРЕННОЕ ЗАКРЫТИЕ ETH: если компенсация не работает в течение 30 минут
        """
        time_in_trade = (current_time - eth_entry_time).total_seconds() / 60
        should_close = eth_pnl < 0 and time_in_trade > 30
        reason = f'emergency_close_after_{time_in_trade:.1f}_minutes' if should_close else ''
        return should_close, reason

    def check_compensation_management(self, btc_pnl: float, eth_pnl: float, current_time: datetime) -> Dict[str, any]:
        """
        УПРАВЛЕНИЕ КОМПЕНСАЦИЕЙ: проверяет все условия закрытия позиций
        Возвращает словарь с решениями
        """
        result = {
            'close_both': False,
            'emergency_close_eth': False,
            'partial_close_btc': False,
            'reason': ''
        }
        
        if self.should_close_both_positions(btc_pnl, eth_pnl):
            result['close_both'] = True
            result['reason'] = 'double_loss_protection'
            return result
        
        if self.state.eth_entry_time:
            emergency_close, emergency_reason = self.should_emergency_close_eth(eth_pnl, self.state.eth_entry_time, current_time)
            if emergency_close:
                result['emergency_close_eth'] = True
                result['reason'] = emergency_reason
                return result
        
        if self.should_partial_close_btc(btc_pnl, eth_pnl):
            result['partial_close_btc'] = True
            result['reason'] = 'successful_compensation'
        
        return result

    def calculate_pnl(self, position: Dict, current_price: float) -> float:
        """
        Рассчитывает PnL позиции с учетом плеча
        """
        if not position:
            return 0.0
        
        entry_price = position['entry_price']
        size = position['size']
        leverage = position.get('leverage', 1)
        
        if position['side'] == 'BUY':
            # Для лонга: (текущая_цена - цена_входа) / цена_входа * размер * плечо
            price_change_pct = (current_price - entry_price) / entry_price
        else:  # SELL
            # Для шорта: (цена_входа - текущая_цена) / цена_входа * размер * плечо
            price_change_pct = (entry_price - current_price) / entry_price
        
        return size * price_change_pct * leverage
