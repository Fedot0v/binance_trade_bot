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
    eth_entry_price: Optional[float] = None
    eth_entry_time: Optional[datetime] = None
    eth_side: Optional[str] = None
    btc_position: Optional[Dict] = None
    eth_position: Optional[Dict] = None
    compensation_triggered: bool = False
    compensation_time: Optional[datetime] = None
    compensation_signal_time: Optional[datetime] = None
    last_btc_price: Optional[float] = None
    btc_candles_against: int = 0
    btc_impulse_detected: bool = False
    partial_close_done: bool = False
    btc_closed_time: Optional[datetime] = None
    # Флаг текущего прогона: был ли когда-либо открыт BTC в ЭТОМ бэктесте
    had_btc: bool = False
    # Идентификатор последней наблюдаемой BTC-сделки (для связи пост-компенсации)
    last_btc_deal_id: Optional[int] = None
    # Для какого BTC deal уже выполнена компенсация (запрет повторного ETH)
    compensation_done_for_deal_id: Optional[int] = None
    
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
        
        self.ema_fast = self.params.get_int("ema_fast", 10)
        self.ema_slow = self.params.get_int("ema_slow", 30)
        self.trend_threshold = self.params.get_float("trend_threshold", 0.001)
        self.btc_risk_pct = self.params.get_float("btc_deposit_prct", 0.05)
        self.btc_stop_loss_pct = self.params.get_float("btc_stop_loss_pct", 0.012)
        self.btc_take_profit_pct = self.params.get_float("btc_take_profit_pct", 0.03)
        self.btc_leverage = self.params.get_int("btc_leverage", 10)
        
        self.eth_risk_pct = self.params.get_float("eth_deposit_prct", 0.1)
        self.eth_stop_loss_pct = self.params.get_float("eth_stop_loss_pct", 0.01)
        self.eth_take_profit_pct = self.params.get_float("eth_take_profit_pct", 0.015)
        self.eth_leverage = self.params.get_int("eth_leverage", 10)
        
        self.compensation_threshold = self.params.get_float("compensation_threshold", 0.005)
        self.compensation_delay_candles = self.params.get_int("compensation_delay_candles", 3)
        self.impulse_threshold = self.params.get_float("impulse_threshold", 0.004)
        self.candles_against_threshold = self.params.get_int("candles_against_threshold", 2)

        # Новые параметры подтверждения и аварийного входа
        self.eth_confirmation_candles = self.params.get_int("eth_confirmation_candles", 3)
        self.require_eth_ema_alignment = self.params.get_bool("require_eth_ema_alignment", True)
        self.eth_volume_min_ratio = self.params.get_float("eth_volume_min_ratio", 0.0)  # 0.0 отключает проверку
        self.high_adverse_threshold = self.params.get_float("high_adverse_threshold", 0.01)  # 1.0% по умолчанию
        self.max_compensation_window_candles = self.params.get_int("max_compensation_window_candles", 30)

        self.trailing_stop_pct = self.params.get_float("trailing_stop_pct", 0.003)
        # Разрешаем компенсацию в короткое окно после закрытия BTC
        self.post_close_compensation_candles = self.params.get_int("post_close_compensation_candles", 5)

        # Направление компенсации по ETH: по умолчанию в ПРОТИВОПОЛОЖНУЮ сторону к BTC
        # True  -> ETH открывается противоположно BTC (хедж)
        # False -> ETH открывается в ту же сторону, что и BTC
        self.eth_compensation_opposite = self.params.get_bool("eth_compensation_opposite", True)

        # Управление болтливостью логов
        self.verbose = self.params.get_bool("verbose", False)

        print("🎛️ Параметры компенсационной стратегии:")
        print(f"   EMA: fast={self.ema_fast} slow={self.ema_slow} threshold={self.trend_threshold*100:.2f}%")
        print(f"   BTC Stop Loss: {self.btc_stop_loss_pct:.4f} ({self.btc_stop_loss_pct*100:.2f}%)")
        print(f"   BTC Take Profit: {self.btc_take_profit_pct:.4f} ({self.btc_take_profit_pct*100:.2f}%)")
        print(f"   BTC Risk %: {self.btc_risk_pct:.4f} ({self.btc_risk_pct*100:.2f}%)")
        print(f"   ETH Stop Loss: {self.eth_stop_loss_pct:.4f} ({self.eth_stop_loss_pct*100:.2f}%)")
        print(f"   ETH Take Profit: {self.eth_take_profit_pct:.4f} ({self.eth_take_profit_pct*100:.2f}%)")
        print(f"   Compensation: threshold={self.compensation_threshold*100:.2f}% candles_against≥{self.candles_against_threshold} delay={self.compensation_delay_candles} max_window={self.max_compensation_window_candles} high_adverse={self.high_adverse_threshold*100:.2f}%")
        print(f"   ETH confirm: candles={self.eth_confirmation_candles} require_alignment={self.require_eth_ema_alignment}")
        print(f"   ETH volume check: {'disabled' if self.eth_volume_min_ratio <= 0 else f'min_ratio={self.eth_volume_min_ratio:.2f}'}")
        print(f"   Trailing stop %: {self.trailing_stop_pct*100:.2f}%")
        print(f"   Post-close window: {self.post_close_compensation_candles} candles")
        print(f"   ETH compensation side: {'opposite' if self.eth_compensation_opposite else 'same'} to BTC")

        self.state = CompensationState()
        self.interval = params.get_str("interval", "1m") # Добавляем интервал свечей

    def required_symbols(self, template=None) -> List[str]:
        """Возвращает список необходимых символов для компенсационной стратегии"""
        return ["BTCUSDT", "ETHUSDT"]

    def _parse_interval_to_minutes(self, interval_str: str) -> int:
        """Парсит строковый интервал ('1m', '5m', '1h', '1d') в минуты."""
        if interval_str.endswith('m'):
            return int(interval_str[:-1])
        elif interval_str.endswith('h'):
            return int(interval_str[:-1]) * 60
        elif interval_str.endswith('d'):
            return int(interval_str[:-1]) * 24 * 60
        else:
            return 1 # По умолчанию 1 минута

    def _get_ema_trend_signal(self, df: pd.DataFrame, ema_fast_span: int, ema_slow_span: int, trend_threshold: float) -> Optional[str]:
        """Вспомогательная функция для генерации сигнала тренда на основе EMA"""
        if len(df) < ema_slow_span:
            if self.verbose:
                print(f"[SIGNAL] BTC hold: недостаточно данных для EMA (len={len(df)} < slow={ema_slow_span})")
            return None

        ema_fast = df['close'].ewm(span=ema_fast_span).mean()
        ema_slow = df['close'].ewm(span=ema_slow_span).mean()

        fast_val = float(ema_fast.iloc[-1])
        slow_val = float(ema_slow.iloc[-1])
        diff = abs(fast_val - slow_val) / slow_val if slow_val != 0 else 0.0
        if self.verbose:
            print(f"[SIGNAL] BTC EMA fast={fast_val:.2f} slow={slow_val:.2f} diff={diff*100:.2f}% threshold={trend_threshold*100:.2f}%")
        if diff < trend_threshold:
            if self.verbose:
                print("[SIGNAL] BTC hold: |EMA_fast-EMA_slow| ниже порога тренда")
            return 'hold'

        trend = 'long' if fast_val > slow_val else 'short'
        if self.verbose:
            print(f"[SIGNAL] BTC тренд: {trend} (EMA_fast {'>' if fast_val > slow_val else '<'} EMA_slow)")
        return trend

    def generate_signal(self, df: pd.DataFrame) -> str:
        """Генерирует сигнал для BTC по логике новичка"""
        signal = self._get_ema_trend_signal(df, self.ema_fast, self.ema_slow, self.trend_threshold)
        final_signal = signal or 'hold'
        if final_signal == 'hold' and signal is None:
            # Уже залогировано внутри _get_ema_trend_signal (недостаточно данных)
            pass
        else:
            if self.verbose:
                print(f"[SIGNAL] BTC итоговый сигнал: {final_signal}")
        return final_signal

    def calculate_position_size(self, balance: float, symbol: str = "BTC") -> float:
        """Рассчитывает размер позиции для BTC или ETH"""
        if symbol == "BTC":
            return balance * self.btc_risk_pct
        else:
            return balance * self.eth_risk_pct
    
    def calculate_stop_loss_price(self, entry_price: float, side: str, symbol: str = "BTC") -> float:
        """Рассчитывает цену стоп-лосса для BTC или ETH.
        Поддерживает значения стороны как 'BUY'/'SELL' и 'long'/'short'.
        """
        sym = (symbol or "BTC").upper()
        is_btc = sym == "BTC" or sym.startswith("BTC")
        stop_loss_pct = self.btc_stop_loss_pct if is_btc else self.eth_stop_loss_pct

        side_upper = (side or "").upper()
        is_long = side_upper in ("BUY", "LONG")

        if is_long:
            return entry_price * (1 - stop_loss_pct)
        return entry_price * (1 + stop_loss_pct)

    def calculate_take_profit_price(self, entry_price: float, side: str, symbol: str = "BTC") -> float:
        """Рассчитывает цену тейк-профита для BTC или ETH.
        Поддерживает значения стороны как 'BUY'/'SELL' и 'long'/'short'.
        """
        sym = (symbol or "BTC").upper()
        is_btc = sym == "BTC" or sym.startswith("BTC")
        take_profit_pct = self.btc_take_profit_pct if is_btc else self.eth_take_profit_pct

        side_upper = (side or "").upper()
        is_long = side_upper in ("BUY", "LONG")

        if is_long:
            return entry_price * (1 + take_profit_pct)
        return entry_price * (1 - take_profit_pct)

    def should_trigger_compensation(self, btc_df: pd.DataFrame, eth_df: pd.DataFrame, current_price: float, current_time: datetime) -> bool:
        """
        УМНАЯ проверка компенсации:
        - BTC идёт против позиции на >= compensation_threshold
        - минимум candles_against_threshold свечей против
        - проходит компенсационная задержка compensation_delay_candles
        - тренд ETH подтверждает направление BTC (EMA)
        - базовые метрики качества (корреляция/направление/объёмы)
        """
        # Разрешаем проверку в двух случаях:
        # 1) BTC позиция активна (btc_deal_id установлен)
        # 2) BTC недавно закрыта (btc_closed_time установлен) и мы в пределах окна пост-компенсации
        if not self.state.btc_entry_price:
            print("[COMP] Нет цены входа по BTC в состоянии — компенсация не рассматривается")
            return False
        if self.state.btc_deal_id is None:
            if not self.state.btc_closed_time:
                if self.verbose:
                    print("[COMP] BTC уже закрыт и нет отметки времени закрытия — компенсация не рассматривается")
                return False
            interval_minutes = self._parse_interval_to_minutes(self.interval)
            candles_since_close = (current_time - self.state.btc_closed_time).total_seconds() / (interval_minutes * 60)
            if candles_since_close > self.post_close_compensation_candles:
                if self.verbose:
                    print(f"[COMP] Истекло пост-окно компенсации: прошло {candles_since_close:.1f} свечей > {self.post_close_compensation_candles}")
                return False
            if self.verbose:
                print(f"[COMP] BTC закрыт недавно ({candles_since_close:.1f} свечей назад) — проверяем компенсацию в пост-окне")

        # Обновляем анализ свечей и импульс
        self._update_candles_analysis(btc_df)
        self._check_impulse(btc_df)
        if self.verbose:
            print(f"[COMP] Анализ компенсации: candles_against={self.state.btc_candles_against} impulse={self.state.btc_impulse_detected}")

        # Рассчитываем неблагоприятное движение в процентах
        if self.state.btc_side == "BUY":
            adverse_pct = (self.state.btc_entry_price - current_price) / self.state.btc_entry_price
        else:
            adverse_pct = (current_price - self.state.btc_entry_price) / self.state.btc_entry_price
        if self.verbose:
            print(f"[COMP] Неблагоприятное движение BTC: {adverse_pct*100:.3f}% | threshold={self.compensation_threshold*100:.2f}%")

        # Должно превысить порог
        if adverse_pct < self.compensation_threshold:
            self.state.compensation_signal_time = None
            if self.verbose:
                print("[COMP] Порог неблагоприятного движения не достигнут — компенсация отклонена")
            return False

        # Достаточное число свечей против
        if self.state.btc_candles_against < self.candles_against_threshold:
            if self.verbose:
                print(f"[COMP] Недостаточно свечей против: {self.state.btc_candles_against} < {self.candles_against_threshold}")
            return False

        # Фиксируем старт компенсационного окна ожидания
        if self.state.compensation_signal_time is None:
            self.state.compensation_signal_time = current_time
            if self.verbose:
                print(f"[COMP] Старт окна ожидания компенсации: t0={self.state.compensation_signal_time}")
            return False

        # Проверяем задержку в свечах
        interval_minutes = self._parse_interval_to_minutes(self.interval)
        candles_passed = (current_time - self.state.compensation_signal_time).total_seconds() / (interval_minutes * 60)
        # Аварийный вход: сильная просадка BTC — можно не ждать подтверждения ETH
        if adverse_pct >= self.high_adverse_threshold:
            if self.verbose:
                print(f"[COMP] Аварийный вход: просадка {adverse_pct*100:.2f}% ≥ {self.high_adverse_threshold*100:.2f}% — разрешаем компенсацию без подтверждения ETH")
            return True

        if candles_passed < self.compensation_delay_candles:
            if self.verbose:
                print(f"[COMP] Ожидание задержки: прошло {candles_passed:.1f} свечей из {self.compensation_delay_candles}")
            return False

        # Ограничение окна ожидания от первого сигнала
        if candles_passed > self.max_compensation_window_candles:
            if self.verbose:
                print(f"[COMP] Истекло окно ожидания компенсации: прошло {candles_passed:.1f} свечей > {self.max_compensation_window_candles}")
            self.state.compensation_signal_time = None
            return False

        # Проверяем тренд ETH
        if eth_df.empty or len(eth_df) < self.ema_slow:
            if self.verbose:
                print("[COMP] Недостаточно ETH данных для подтверждения тренда")
            return False

        eth_trend = self._get_ema_trend_signal(eth_df, self.ema_fast, self.ema_slow, self.trend_threshold)
        btc_trend = 'long' if self.state.btc_side == 'BUY' else 'short'
        expected_eth_trend = ('short' if btc_trend == 'long' else 'long') if self.eth_compensation_opposite else btc_trend
        if self.require_eth_ema_alignment and eth_trend != expected_eth_trend:
            if self.verbose:
                print(f"[COMP] ETH тренд не соответствует ожидаемому: eth={eth_trend} vs expected_eth={expected_eth_trend} (btc={btc_trend}, mode={'opposite' if self.eth_compensation_opposite else 'same'})")
            return False

        # Подтверждение последними N свечами ETH в сторону BTC
        n = max(1, int(self.eth_confirmation_candles))
        if len(eth_df) < n:
            if self.verbose:
                print(f"[COMP] Недостаточно ETH свечей для подтверждения: {len(eth_df)} < {n}")
            return False
        eth_last = eth_df.iloc[-n:]
        # Подтверждаем направление именно для ETH-стороны компенсации
        eth_side_for_entry = self.get_eth_side()
        if eth_side_for_entry == 'BUY':
            green_count = int((eth_last['close'] > eth_last['open']).sum())
            dir_ok = green_count == n and float(eth_last['close'].iloc[-1]) > float(eth_last['close'].iloc[0])
        else:
            red_count = int((eth_last['close'] < eth_last['open']).sum())
            dir_ok = red_count == n and float(eth_last['close'].iloc[-1]) < float(eth_last['close'].iloc[0])
        if not dir_ok:
            if self.verbose:
                print(f"[COMP] ETH не подтвердил {n} свечами направление компенсации ({eth_side_for_entry}) — компенсация отклонена")
            return False

        # Минимальное подтверждение объёмами ETH (по желанию)
        if self.eth_volume_min_ratio > 0:
            recent_vol = float(eth_last['volume'].mean())
            base_window = min(len(eth_df) - n, n * 4)
            if base_window <= 0:
                if self.verbose:
                    print("[COMP] Недостаточно исторических данных ETH для оценки объёма")
                return False
            base_vol = float(eth_df['volume'].iloc[-(n+base_window):-n].mean())
            vol_ratio = recent_vol / base_vol if base_vol > 0 else 0.0
            if vol_ratio < self.eth_volume_min_ratio:
                if self.verbose:
                    print(f"[COMP] Объём ETH слабый: ratio={vol_ratio:.2f} < {self.eth_volume_min_ratio:.2f}")
                return False

        # Базовая проверка качества компенсационного сигнала
        quality = self.get_compensation_quality_score(btc_df, eth_df)
        if self.verbose:
            print(f"[COMP] Качество сигнала: corr_ok={quality.get('correlation_ok')} eth_dir_ok={quality.get('eth_direction_ok')} score={quality.get('score')}")
        if not (quality.get("correlation_ok") and quality.get("eth_direction_ok")):
            if self.verbose:
                print("[COMP] Качество компенсационного сигнала недостаточно — компенсация отклонена")
            return False

        return True

    def mark_btc_closed(self, current_time: datetime) -> None:
        """Помечает BTC как недавно закрытую, чтобы разрешить пост-компенсацию.
        Разрешаем только если в этом бэктесте уже был реальный вход в BTC (had_btc=True).
        """
        if not getattr(self.state, 'had_btc', False):
            # Игнорируем попытки пометить закрытие до первого реального входа BTC в этом прогоне
            return
        if not self.state.btc_closed_time:
            self.state.btc_closed_time = current_time
            print(f"[COMP] BTC позиция помечена как закрытая: t_close={self.state.btc_closed_time}")

    def can_compensate_after_close(self, current_time: datetime) -> bool:
        """Можно ли ещё проверять компенсацию после закрытия BTC (в пределах окна)."""
        if not self.state.btc_closed_time:
            return False
        interval_minutes = self._parse_interval_to_minutes(self.interval)
        candles_since_close = (current_time - self.state.btc_closed_time).total_seconds() / (interval_minutes * 60)
        return candles_since_close <= self.post_close_compensation_candles

    def get_compensation_quality_score(self, btc_df: pd.DataFrame, eth_df: pd.DataFrame) -> Dict[str, float]:
        """
        Оценивает качество сигнала компенсации
        Возвращает словарь с метриками качества
        """
        if len(btc_df) < 20 or len(eth_df) < 20:
            return {"volume_ok": False, "correlation_ok": False, "eth_direction_ok": False, "score": 0.0}
        
        btc_last_time = btc_df.index[-1]
        eth_last_time = eth_df.index[-1]
        
        time_diff = abs((btc_last_time - eth_last_time).total_seconds())
        if time_diff > 60:
            return {"volume_ok": False, "correlation_ok": False, "eth_direction_ok": False, "score": 0.0}
        
        btc_current_time = btc_df.index[-1]
        
        eth_time_diff = abs(eth_df.index - btc_current_time)
        eth_current_idx = eth_time_diff.argmin()
        
        btc_volume_ratio = btc_df['volume'].iloc[-5:].mean() / btc_df['volume'].iloc[-20:].mean()
        
        if eth_current_idx >= 19:
            eth_volume_ratio = eth_df['volume'].iloc[eth_current_idx-4:eth_current_idx+1].mean() / eth_df['volume'].iloc[eth_current_idx-19:eth_current_idx+1].mean()
        else:
            eth_volume_ratio = 1.0
        
        if len(btc_df) >= 10 and eth_current_idx >= 9:
            btc_prices = btc_df['close'].iloc[-10:].values
            eth_prices = eth_df['close'].iloc[eth_current_idx-9:eth_current_idx+1].values
            correlation = pd.Series(btc_prices).corr(pd.Series(eth_prices))
        else:
            correlation = 0.8
        
        eth_direction_ok = False
        if len(eth_df) >= 5:
            eth_side = self.get_eth_side()
            
            btc_current_time = btc_df.index[-1]
            eth_current_time = eth_df.index[-1]
            
            if abs((btc_current_time - eth_current_time).total_seconds()) > 120:
                return {
                    "volume_ok": volume_ok,
                    "correlation_ok": correlation_ok,
                    "eth_direction_ok": False,
                    "btc_volume_ratio": btc_volume_ratio,
                    "eth_volume_ratio": eth_volume_ratio,
                    "correlation": correlation,
                    "score": 0.0
                }
            
            btc_current_time = btc_df.index[-1]
            
            eth_time_diff = abs(eth_df.index - btc_current_time)
            eth_current_idx = eth_time_diff.argmin()
            
            if eth_current_idx >= 4:
                eth_prices = eth_df['close'].iloc[eth_current_idx-4:eth_current_idx+1].values
                eth_volumes = eth_df['volume'].iloc[eth_current_idx-2:eth_current_idx+1].values
            else:
                eth_prices = eth_df['close'].iloc[:eth_current_idx+1].values
                eth_volumes = eth_df['volume'].iloc[:eth_current_idx+1].values
            
            if eth_side == "BUY":
                price_trend = eth_prices[4] > eth_prices[0]
                volume_confirmation = eth_volumes[2] > eth_volumes[0] * 0.5
                if price_trend and volume_confirmation:
                    eth_direction_ok = True
            elif eth_side == "SELL":
                price_trend = eth_prices[4] < eth_prices[0]
                volume_confirmation = eth_volumes[2] > eth_volumes[0] * 0.5
                if price_trend and volume_confirmation:
                    eth_direction_ok = True
        
        volume_ok = btc_volume_ratio > 0.5 and eth_volume_ratio > 0.5
        correlation_ok = correlation > 0.2
        
        quality_score = 0.0
        if volume_ok:
            quality_score += 25
        if correlation_ok:
            quality_score += 25
        if eth_direction_ok:
            quality_score += 50
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
        if price_change_pct > 0.005:
            return 1.2
        elif price_change_pct > 0.003:
            return 1.1
        else:
            return 0.8

    def should_partial_close_btc(self, btc_pnl: float, eth_pnl: float) -> bool:
        """
        Проверяет, нужно ли частично закрыть BTC при успешной компенсации
        """
        return eth_pnl > 0 and abs(eth_pnl) > abs(btc_pnl) * 0.5

    def should_close_both_positions(self, btc_pnl: float, eth_pnl: float) -> bool:
        """
        ЗАЩИТА ОТ ДВОЙНОГО УБЫТКА: закрывает обе позиции если обе в убытке
        """
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
            new_stop = current_price * (1 - self.trailing_stop_pct)
            return max(position.get('trailing_stop', position['stop_loss']), new_stop)
        else:
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
            
            if candle['close'] > candle['open']:
                candle_direction = "up"
            else:
                candle_direction = "down"
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
        
        price_change_pct = abs(current_candle['close'] - prev_candle['close']) / prev_candle['close']
        
        if self.state.btc_side == "BUY" and current_candle['close'] < prev_candle['close']:
            if price_change_pct > self.impulse_threshold:
                self.state.btc_impulse_detected = True
        elif self.state.btc_side == "SELL" and current_candle['close'] > prev_candle['close']:
            if price_change_pct > self.impulse_threshold:
                self.state.btc_impulse_detected = True

    def should_close_btc_position(self, btc_df: pd.DataFrame, current_time: datetime) -> Tuple[bool, str]:
        """
        Проверяет, нужно ли закрыть позицию BTC (ВСЕ УСЛОВИЯ ЗАКРЫТИЯ)
        Возвращает (нужно_закрыть, причина)
        """
        # print(f"🔍 Вызван should_close_btc_position: deal_id={self.state.btc_deal_id}, entry_price={self.state.btc_entry_price}")

        if not self.state.btc_entry_price:
            # print("❌ Нет данных о позиции BTC (нет цены входа)")
            return False, ""

        if self.state.btc_deal_id is None:
            # print("❌ Нет данных о позиции BTC (deal_id is None)")
            return False, ""

        current_btc_price = btc_df['close'].iloc[-1]

        btc_position = {
            'side': self.state.btc_side,
            'take_profit': self.calculate_take_profit_price(self.state.btc_entry_price, self.state.btc_side, 'BTC'),
            'stop_loss': self.calculate_stop_loss_price(self.state.btc_entry_price, self.state.btc_side, 'BTC'),
            'trailing_stop': self.calculate_stop_loss_price(self.state.btc_entry_price, self.state.btc_side, 'BTC'),
            'entry_time': self.state.btc_entry_time
        }

        # Отладочная информация о проверке закрытия
        # print(f"🔍 Проверка закрытия BTC позиции:")
        # print(f"   Текущая цена BTC: ${current_btc_price:.2f}")
        # print(f"   Цена входа: ${self.state.btc_entry_price:.2f}")
        # print(f"   Сторона: {btc_position['side']}")
        # print(f"   Take Profit: ${btc_position['take_profit']:.2f}")
        # print(f"   Stop Loss: ${btc_position['stop_loss']:.2f}")
        # print(f"   Изменение цены: {(current_btc_price - self.state.btc_entry_price) / self.state.btc_entry_price * 100:.2f}%")
        
        if (btc_position['side'] == 'BUY' and current_btc_price >= btc_position['take_profit']) or \
           (btc_position['side'] == 'SELL' and current_btc_price <= btc_position['take_profit']):
            # print(f"🎯 ТЕЙК-ПРОФИТ! Цена {current_btc_price} {'выше' if btc_position['side'] == 'BUY' else 'ниже'} уровня {btc_position['take_profit']}")
            return True, "take_profit"
        
        if (btc_position['side'] == 'BUY' and current_btc_price <= btc_position['trailing_stop']) or \
           (btc_position['side'] == 'SELL' and current_btc_price >= btc_position['trailing_stop']):
            return True, "trailing_stop"
        
        if (btc_position['side'] == 'BUY' and current_btc_price <= btc_position['stop_loss']) or \
           (btc_position['side'] == 'SELL' and current_btc_price >= btc_position['stop_loss']):
            # print(f"🛑 СТОП-ЛОСС! Цена {current_btc_price} {'ниже' if btc_position['side'] == 'BUY' else 'выше'} уровня {btc_position['stop_loss']}")
            return True, "stop_loss"
        
        if self.state.btc_entry_price and self.state.btc_entry_time:
            if self.state.btc_side == 'BUY':
                trailing_stop = current_btc_price * (1 - self.trailing_stop_pct)
            else:
                trailing_stop = current_btc_price * (1 + self.trailing_stop_pct)
            if (btc_position['side'] == 'BUY' and current_btc_price <= trailing_stop) or \
               (btc_position['side'] == 'SELL' and current_btc_price >= trailing_stop):
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

        # Фиксируем сторону ETH на момент входа, чтобы закрытие не зависело от текущего состояния BTC
        eth_side = self.state.eth_side or self.get_eth_side()

        if hasattr(self.state, 'eth_entry_price') and self.state.eth_entry_price:
            eth_entry_price = self.state.eth_entry_price
        else:
            eth_entry_price = current_eth_price

        take_profit_price = self.calculate_take_profit_price(eth_entry_price, eth_side, 'ETH')
        stop_loss_price = self.calculate_stop_loss_price(eth_entry_price, eth_side, 'ETH')

        # print(f"🔍 DEBUG: ETH Close Check | Side: {eth_side} | Entry: {eth_entry_price:.2f} | Current: {current_eth_price:.2f}")
        # print(f"🔍 DEBUG: ETH Levels | TP: {take_profit_price:.2f} | SL: {stop_loss_price:.2f}")

        if (eth_side == 'BUY' and current_eth_price >= take_profit_price) or \
           (eth_side == 'SELL' and current_eth_price <= take_profit_price):
            return True, "take_profit"

        if (eth_side == 'BUY' and current_eth_price <= stop_loss_price) or \
           (eth_side == 'SELL' and current_eth_price >= stop_loss_price):
            return True, "stop_loss"

        if eth_side == 'BUY':
            trailing_stop = current_eth_price * (1 - self.trailing_stop_pct)
        else:
            trailing_stop = current_eth_price * (1 + self.trailing_stop_pct)

        if (eth_side == 'BUY' and current_eth_price <= trailing_stop) or \
           (eth_side == 'SELL' and current_eth_price >= trailing_stop):
            # print(f"📈 ETH TRAILING-STOP! Цена {current_eth_price:.2f} достигла уровня {trailing_stop:.2f}")
            return True, "trailing_stop"

        if self.state.eth_entry_time:
            emergency_close, emergency_reason = self.should_emergency_close_eth(0, self.state.eth_entry_time, current_time)
            if emergency_close:
                # print(f"🚨 ETH EMERGENCY CLOSE! {emergency_reason}")
                return True, emergency_reason

        # Дополнительная логика: если тренд ETH расходится с направлением позиции — быстро закрываем
        if len(eth_df) >= self.ema_slow and self.state.eth_entry_time:
            interval_minutes = self._parse_interval_to_minutes(self.interval)
            candles_since_entry = (current_time - self.state.eth_entry_time).total_seconds() / (interval_minutes * 60)
            # Ждём минимум 2 свечи после входа, затем проверяем тренд на расхождение
            if candles_since_entry >= max(2, self.compensation_delay_candles // 2):
                eth_trend = self._get_ema_trend_signal(eth_df, self.ema_fast, self.ema_slow, self.trend_threshold)
                expected_trend = 'long' if eth_side == 'BUY' else 'short'
                if eth_trend and eth_trend != expected_trend:
                    return True, "eth_trend_mismatch"

        return False, ""



    def get_eth_side(self) -> str:
        """Возвращает сторону для ETH в соответствии с режимом компенсации.
        Если eth_compensation_opposite=True — в противоположную сторону к BTC, иначе в ту же сторону.
        """
        btc_side = self.state.btc_side
        if btc_side is None:
            return 'BUY'
        if self.eth_compensation_opposite:
            return 'SELL' if btc_side == 'BUY' else 'BUY'
        return btc_side


    def update_state(self, btc_deal_id: Optional[int] = None,
                    eth_deal_id: Optional[int] = None,
                    btc_entry_price: Optional[float] = None,
                    btc_entry_time: Optional[datetime] = None,
                    btc_side: Optional[str] = None,
                    eth_entry_price: Optional[float] = None,
                    eth_entry_time: Optional[datetime] = None,
                    eth_side: Optional[str] = None,
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
        if eth_side is not None:
            self.state.eth_side = eth_side
        if compensation_triggered:
            self.state.compensation_triggered = True
            self.state.compensation_time = datetime.now()

    def reset_state(self) -> None:
        """Сбрасывает состояние стратегии"""
        self.state = CompensationState()

    # Новое: явные методы очистки состояний BTC/ETH, когда позиции закрыты
    def clear_btc_state(self) -> None:
        self.state.btc_deal_id = None
        self.state.btc_entry_price = None
        self.state.btc_entry_time = None
        self.state.btc_side = None
        # При отсутствии BTC сбрасываем и компенсационные таймеры/флаги
        self.state.compensation_triggered = False
        self.state.compensation_time = None
        self.state.compensation_signal_time = None
        self.state.btc_candles_against = 0
        self.state.btc_impulse_detected = False

    def clear_eth_state(self) -> None:
        self.state.eth_deal_id = None
        self.state.eth_entry_price = None
        self.state.eth_entry_time = None
        self.state.eth_side = None

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
            price_change_pct = (current_price - entry_price) / entry_price
        else:
            price_change_pct = (entry_price - current_price) / entry_price
        
        return size * price_change_pct * leverage
