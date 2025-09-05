#!/usr/bin/env python3
"""
Бэктест стратегии "Компенсация и реакция" на реальных данных

Использует CSV файлы с минутными свечами BTC и ETH для тестирования стратегии
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os
from typing import Dict, List, Tuple, Optional

# Добавляем путь к модулям приложения
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from strategies.compensation_strategy import CompensationStrategy
from services.strategy_parameters import StrategyParameters


class BacktestResult:
    def __init__(self):
        self.trades: List[Dict] = []
        self.btc_trades: List[Dict] = []
        self.eth_trades: List[Dict] = []
        self.total_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.max_drawdown = 0.0
        self.peak_balance = 0.0
        self.current_balance = 10000.0  # Начальный баланс $10,000

    def add_trade(self, trade: Dict):
        self.trades.append(trade)
        self.total_trades += 1
        
        pnl = trade.get('pnl', 0)
        self.total_pnl += pnl
        self.current_balance += pnl
        
        if pnl > 0:
            self.winning_trades += 1
        elif pnl < 0:
            self.losing_trades += 1
            
        # Обновляем максимальный баланс и просадку
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
        
        drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def print_summary(self):
        print("\n" + "="*60)
        print("РЕЗУЛЬТАТЫ БЭКТЕСТА СТРАТЕГИИ 'КОМПЕНСАЦИЯ И РЕАКЦИЯ'")
        print("="*60)
        
        print(f"Начальный баланс: ${10000:,.2f}")
        print(f"Конечный баланс: ${self.current_balance:,.2f}")
        print(f"Общая прибыль/убыток: ${self.total_pnl:,.2f}")
        print(f"Доходность: {(self.total_pnl / 10000) * 100:.2f}%")
        print(f"Максимальная просадка: {self.max_drawdown * 100:.2f}%")
        
        print(f"\nВсего сделок: {self.total_trades}")
        print(f"Прибыльных сделок: {self.winning_trades}")
        print(f"Убыточных сделок: {self.losing_trades}")
        
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
            print(f"Процент прибыльных сделок: {win_rate:.1f}%")
            
            avg_win = sum(t['pnl'] for t in self.trades if t['pnl'] > 0) / max(1, self.winning_trades)
            avg_loss = sum(t['pnl'] for t in self.trades if t['pnl'] < 0) / max(1, self.losing_trades)
            print(f"Средняя прибыль: ${avg_win:.2f}")
            print(f"Средний убыток: ${avg_loss:.2f}")
            
            if avg_loss != 0:
                profit_factor = abs(avg_win * self.winning_trades / (avg_loss * self.losing_trades))
                print(f"Profit Factor: {profit_factor:.2f}")


def load_csv_data(filename: str) -> pd.DataFrame:
    """Загружает CSV данные и приводит к нужному формату"""
    print(f"Загрузка данных из {filename}...")
    
    # Пробуем разные форматы CSV
    try:
        df = pd.read_csv(filename)
    except Exception as e:
        print(f"Ошибка загрузки {filename}: {e}")
        return pd.DataFrame()
    
    print(f"Загружено {len(df)} записей")
    print(f"Колонки: {list(df.columns)}")
    
    # Приводим к стандартному формату
    column_mapping = {
        'timestamp': 'timestamp',
        'open': 'open',
        'high': 'high', 
        'low': 'low',
        'close': 'close',
        'volume': 'volume'
    }
    
    # Переименовываем колонки если нужно
    for old_col, new_col in column_mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df[new_col] = df[old_col]
    
    # Конвертируем timestamp
    if 'open_time' in df.columns:
        # Проверяем, нужно ли конвертировать из миллисекунд или уже datetime
        if df['open_time'].dtype == 'object':
            # Уже в формате datetime, просто конвертируем
            df['timestamp'] = pd.to_datetime(df['open_time'])
        else:
            # В миллисекундах, конвертируем
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        df.set_index('timestamp', inplace=True)
    elif 'timestamp' in df.columns:
        if df['timestamp'].dtype == 'object':
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        else:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
    
    # Проверяем наличие необходимых колонок
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        print(f"Отсутствуют колонки: {missing_cols}")
        return pd.DataFrame()
    
    print(f"Данные загружены: {df.index.min()} - {df.index.max()}")
    return df


def simulate_eth_data(btc_df: pd.DataFrame, correlation: float = 0.8) -> pd.DataFrame:
    """Создает симулированные данные ETH на основе BTC с корреляцией"""
    print("Создание симулированных данных ETH...")
    
    # Берем изменения цены BTC
    btc_returns = btc_df['close'].pct_change().fillna(0)
    
    # Создаем коррелированные изменения для ETH
    np.random.seed(42)  # Для воспроизводимости
    eth_returns = correlation * btc_returns + np.sqrt(1 - correlation**2) * np.random.normal(0, 0.01, len(btc_returns))
    
    # Создаем цены ETH (начинаем с $3000)
    eth_prices = [3000]
    for ret in eth_returns[1:]:
        eth_prices.append(eth_prices[-1] * (1 + ret))
    
    # Создаем DataFrame для ETH
    eth_df = btc_df.copy()
    eth_df['close'] = eth_prices
    eth_df['open'] = eth_df['close'] * (1 + np.random.normal(0, 0.002, len(eth_df)))
    eth_df['high'] = eth_df[['open', 'close']].max(axis=1) * (1 + abs(np.random.normal(0, 0.001, len(eth_df))))
    eth_df['low'] = eth_df[['open', 'close']].min(axis=1) * (1 - abs(np.random.normal(0, 0.001, len(eth_df))))
    eth_df['volume'] = np.random.randint(1000, 10000, len(eth_df))
    
    print(f"ETH данные созданы: цена от ${eth_df['close'].min():.2f} до ${eth_df['close'].max():.2f}")
    return eth_df


def run_backtest(btc_df: pd.DataFrame, eth_df: pd.DataFrame, params: Dict) -> BacktestResult:
    """Запускает бэктест стратегии"""
    print("\nЗапуск бэктеста...")
    
    strategy = CompensationStrategy(StrategyParameters(params))
    result = BacktestResult()
    
    # Состояние позиций
    btc_position = None
    eth_position = None
    last_trade_time = None  # Время последней сделки
    
    # Проходим по всем свечам
    for i in range(50, len(btc_df)):  # Начинаем с 50-й свечи для достаточного количества данных
        current_time = btc_df.index[i]
        btc_data = btc_df.iloc[:i+1]
        eth_data = eth_df.iloc[:i+1]
        
        current_btc_price = btc_data['close'].iloc[-1]
        current_eth_price = eth_data['close'].iloc[-1]
        
        # Если нет открытых позиций, проверяем сигнал на вход в BTC
        if not btc_position:
            signal = strategy.generate_signal(btc_data)
            
            # Дополнительная фильтрация: проверяем тренд на больших таймфреймах
            if len(btc_data) >= 60:  # Нужно минимум 60 свечей для анализа
                # Проверяем тренд на 30-минутном таймфрейме
                thirty_min_data = btc_data.iloc[-30:]
                thirty_min_trend = strategy.generate_signal(thirty_min_data)
                
                # Входим только если сигналы совпадают и прошло достаточно времени с последней сделки
                if signal in ['long', 'short'] and signal == thirty_min_trend:
                    # Дополнительная проверка: объем должен быть выше среднего за последние 30 свечей
                    recent_volume = btc_data['volume'].iloc[-30:].mean()
                    current_volume = btc_data['volume'].iloc[-1]
                    volume_confirmed = current_volume > recent_volume * 1.1  # Объем на 10% выше среднего
                    
                    # Простая проверка RSI (избегаем экстремальных значений)
                    price_changes = btc_data['close'].diff().iloc[-14:]  # Последние 14 свечей
                    gains = price_changes.where(price_changes > 0, 0).mean()
                    losses = -price_changes.where(price_changes < 0, 0).mean()
                    rs = gains / losses if losses != 0 else 100
                    rsi = 100 - (100 / (1 + rs))
                    rsi_confirmed = 25 < rsi < 75  # Более широкая нейтральная зона
                    
                    if volume_confirmed and rsi_confirmed:
                        # Проверяем, прошло ли достаточно времени с последней сделки (минимум 45 минут)
                        if last_trade_time is None or (current_time - last_trade_time).total_seconds() / 60 >= 45:
                            side = 'BUY' if signal == 'long' else 'SELL'
                            btc_position = {
                                'entry_time': current_time,
                                'entry_price': current_btc_price,
                                'side': side,
                                'size': result.current_balance * params['btc_deposit_prct'],
                                'leverage': params['btc_leverage'],
                                'stop_loss': strategy.calculate_stop_loss_price(current_btc_price, side, 'BTC'),
                                'take_profit': strategy.calculate_take_profit_price(current_btc_price, side, 'BTC'),
                                'trailing_stop': strategy.calculate_stop_loss_price(current_btc_price, side, 'BTC')
                            }
                        
                            print(f"Вход в BTC: {signal.upper()} по ${current_btc_price:.2f}")
                            print(f"  Стоп-лосс: ${btc_position['stop_loss']:.2f}")
                            print(f"  Тейк-профит: ${btc_position['take_profit']:.2f}")
                            print(f"  Размер позиции: ${btc_position['size']:.2f}")
                            print(f"  Объем подтвержден: {current_volume:.0f} > {recent_volume*1.1:.0f}")
                            print(f"  RSI: {rsi:.1f} (нейтральная зона)")
                        
                            # Обновляем состояние стратегии
                            strategy.update_state(
                                btc_deal_id=len(result.trades) + 1,
                                btc_entry_price=current_btc_price,
                                btc_entry_time=current_time.to_pydatetime(),
                                btc_side=btc_position['side']
                            )
        
        # Если есть позиция BTC, проверяем компенсацию
        elif btc_position and not eth_position:
            # Рассчитываем движение цены для отладки
            price_change_pct = abs(current_btc_price - btc_position['entry_price']) / btc_position['entry_price']
            time_since_entry = (current_time - btc_position['entry_time']).total_seconds() / 60
            
            # Отладочная информация каждые 10 минут
            if int(time_since_entry) % 10 == 0 and int(time_since_entry) > 0:
                print(f"  Проверка компенсации: цена ${current_btc_price:.2f}, изменение {price_change_pct*100:.3f}%, время {time_since_entry:.1f}мин")
            
            # УМНАЯ КОМПЕНСАЦИЯ: используем стратегию для принятия решений
            compensation_result = strategy.should_trigger_compensation(btc_data, current_btc_price, current_time)
            
            # Детальная отладка если движение > 0.1%
            if price_change_pct > 0.001:
                print(f"    Детальная проверка компенсации:")
                print(f"      Движение цены: {price_change_pct*100:.3f}% (порог: 0.1%)")
                print(f"      Время с входа: {time_since_entry:.1f}мин (лимит: 30мин)")
                print(f"      Движение против позиции: {current_btc_price < btc_position['entry_price'] if btc_position['side'] == 'BUY' else current_btc_price > btc_position['entry_price']}")
                print(f"      Свечи против: {strategy.state.btc_candles_against} (нужно: 2)")
                print(f"      Импульс обнаружен: {strategy.state.btc_impulse_detected}")
                print(f"      РЕЗУЛЬТАТ КОМПЕНСАЦИИ: {compensation_result}")
            
            if compensation_result:
                # ОЦЕНКА КАЧЕСТВА КОМПЕНСАЦИИ через стратегию
                quality_score = strategy.get_compensation_quality_score(btc_data, eth_data)
                
                print(f"    📈 Объем BTC: {quality_score['btc_volume_ratio']:.2f}x, ETH: {quality_score['eth_volume_ratio']:.2f}x")
                print(f"    🔗 Корреляция BTC/ETH: {quality_score['correlation']:.3f}")
                print(f"    🎯 Направление ETH: {'✅' if quality_score['eth_direction_ok'] else '❌'}")
                print(f"    🎯 Общий скор качества: {quality_score['score']:.1f}/100")
                
                # Фильтруем по качеству сигнала (снижен порог для более частых компенсаций)
                if quality_score['score'] >= 40:  # Минимальный скор качества (СНИЖЕН для более частых компенсаций)
                    # СОЗДАЕМ ПОЗИЦИЮ КОМПЕНСАЦИИ через стратегию
                    eth_position = strategy.create_compensation_position(
                        current_eth_price, current_time, price_change_pct, result.current_balance
                    )
                    
                    print(f"Компенсация ETH: {eth_position['side']} по ${current_eth_price:.2f}")
                    print(f"  Размер: ${eth_position['size']:.2f} (множитель: {eth_position['size_multiplier']}x)")
                    print(f"  Стоп-лосс: ${eth_position['stop_loss']:.2f}")
                    print(f"  Тейк-профит: ${eth_position['take_profit']:.2f}")
                    
                    strategy.update_state(
                        eth_deal_id=len(result.trades) + 2,
                        compensation_triggered=True
                    )
                else:
                    print(f"    ❌ КОМПЕНСАЦИЯ ОТМЕНЕНА: низкий скор качества ({quality_score['score']:.1f}/100)")
        
        # ПРОВЕРКА ЗАКРЫТИЯ BTC через стратегию
        if btc_position:
            # Обновляем trailing stop и синхронизируем состояние
            btc_position['trailing_stop'] = strategy.update_trailing_stop(btc_position, current_btc_price)
            strategy.state.btc_position = btc_position
            
            # Проверяем все условия закрытия через стратегию
            should_close_btc, close_reason = strategy.should_close_btc_position(btc_data, current_time)
            if should_close_btc:
                pnl = strategy.calculate_pnl(btc_position, current_btc_price)
                result.add_trade({
                    'symbol': 'BTCUSDT',
                    'entry_time': btc_position['entry_time'],
                    'exit_time': current_time,
                    'entry_price': btc_position['entry_price'],
                    'exit_price': current_btc_price,
                    'side': btc_position['side'],
                    'pnl': pnl,
                    'reason': close_reason
                })
                
                print(f"Закрытие BTC по {close_reason}: ${current_btc_price:.2f}, PnL: ${pnl:.2f}")
                last_trade_time = current_time
                btc_position = None
                eth_position = None
                strategy.state.reset_state()
                continue
        
        if eth_position:
            # УПРАВЛЕНИЕ КОМПЕНСАЦИЕЙ через стратегию
            btc_pnl = strategy.calculate_pnl(btc_position, current_btc_price) if btc_position else 0
            eth_pnl = strategy.calculate_pnl(eth_position, current_eth_price)
            
            # Проверяем все условия управления через стратегию
            management = strategy.check_compensation_management(btc_pnl, eth_pnl, current_time)
            
            if management['close_both']:
                print(f"🚨 ЗАКРЫТИЕ ОБЕИХ ПОЗИЦИЙ ({management['reason']}): BTC ${btc_pnl:.2f}, ETH ${eth_pnl:.2f}")
                btc_position = None
                eth_position = None
                strategy.state.reset_state()
                continue
            elif management['emergency_close_eth']:
                print(f"🚨 ЭКСТРЕННОЕ ЗАКРЫТИЕ ETH ({management['reason']}): ${current_eth_price:.2f}, PnL: ${eth_pnl:.2f}")
                eth_position = None
                strategy.state.eth_position = None
                continue
            elif management['partial_close_btc']:
                print(f"    🎯 УСПЕШНАЯ КОМПЕНСАЦИЯ: ETH PnL ${eth_pnl:.2f} > BTC PnL ${btc_pnl:.2f}")
                # Частичное закрытие BTC через стратегию
                if btc_position and not btc_position.get('partial_close_done', False):
                    btc_position['partial_close_done'] = True
                    btc_position['size'] *= 0.5
                    print(f"    ✂️ Частичное закрытие BTC: оставшийся размер ${btc_position['size']:.2f}")
            
            # Обновляем trailing stop через стратегию
            eth_position['trailing_stop'] = strategy.update_trailing_stop(eth_position, current_eth_price)
            
            # ПРОВЕРКА ЗАКРЫТИЯ ETH через стратегию
            should_close_eth, close_reason = strategy.should_close_eth_position(eth_data, current_time)
            if should_close_eth and eth_position:
                pnl = strategy.calculate_pnl(eth_position, current_eth_price)
                result.add_trade({
                    'symbol': 'ETHUSDT',
                    'entry_time': eth_position['entry_time'],
                    'exit_time': current_time,
                    'entry_price': eth_position['entry_price'],
                    'exit_price': current_eth_price,
                    'side': eth_position['side'],
                    'pnl': pnl,
                    'reason': close_reason
                })
                
                print(f"Закрытие ETH по {close_reason}: ${current_eth_price:.2f}, PnL: ${pnl:.2f}")
                eth_position = None
                strategy.state.eth_position = None
    
    # Закрываем оставшиеся позиции
    if btc_position:
        pnl = strategy.calculate_pnl(btc_position, current_btc_price)
        result.add_trade({
            'symbol': 'BTCUSDT',
            'entry_time': btc_position['entry_time'],
            'exit_time': btc_df.index[-1],
            'entry_price': btc_position['entry_price'],
            'exit_price': current_btc_price,
            'side': btc_position['side'],
            'pnl': pnl,
            'reason': 'end_of_data'
        })
    
    if eth_position:
        pnl = strategy.calculate_pnl(eth_position, current_eth_price)
        result.add_trade({
            'symbol': 'ETHUSDT',
            'entry_time': eth_position['entry_time'],
            'exit_time': eth_df.index[-1],
            'entry_price': eth_position['entry_price'],
            'exit_price': current_eth_price,
            'side': eth_position['side'],
            'pnl': pnl,
            'reason': 'end_of_data'
        })
    
    return result





def main():
    print("=== БЭКТЕСТ УМНОЙ СТРАТЕГИИ 'КОМПЕНСАЦИЯ И РЕАКЦИЯ' ===")
    
    # Параметры стратегии (ПРИВЕДЕНЫ В СООТВЕТСТВИЕ С ОРИГИНАЛОМ)
    params = {
        "ema_fast": 10,
        "ema_slow": 30,
        "trend_threshold": 0.0015,  # Сбалансированный порог 0.15%
        "btc_deposit_prct": 0.15,  # 15% от баланса = $1500 (как в оригинале)
        "btc_leverage": 10,        # Кредитное плечо x10
        "btc_stop_loss_pct": 0.008,  # 0.8% (уменьшен для снижения убытков)
        "btc_take_profit_pct": 0.03,  # 3.0% (с учетом плеча = 30% от депозита)
        "eth_deposit_prct": 0.2,   # 20% от баланса = $2000 (снижен для уменьшения убытков)
        "eth_leverage": 10,        # Кредитное плечо x10
        "eth_stop_loss_pct": 0.007,  # 0.7% (уменьшен для снижения убытков)
        "eth_take_profit_pct": 0.015,  # 1.5% (с учетом плеча = 15% от депозита)
        "compensation_threshold": 0.001,  # 0.1% (снижен для более частых компенсаций)
        "compensation_delay_candles": 2,  # Ждать 2 свечи перед компенсацией (уменьшено)
        "impulse_threshold": 0.003,  # 0.3% (снижен для более частых импульсов)
        "candles_against_threshold": 1,  # Снижено с 2 до 1 для более частых компенсаций
        "trailing_stop_pct": 0.002,  # 0.2% (уменьшен для лучшей защиты прибыли)

    }
    
    # Загружаем данные BTC за последние два месяца
    print("Тестируем на данных с апреля по август 2025 года (5 месяцев, оптимизированная стратегия)")
    
    btc_df = load_csv_data("BTCUSDT-1m-april-august-2025.csv")
    if btc_df.empty:
        print("Не удалось загрузить данные BTC")
        return
    
    # Загружаем РЕАЛЬНЫЕ данные ETH с апреля по август 2025 года
    eth_df = load_csv_data("ETHUSDT-1m-april-august-2025.csv")
    if eth_df.empty:
        print("Не удалось загрузить данные ETH, используем симуляцию...")
        eth_df = simulate_eth_data(btc_df, correlation=0.8)
    else:
        print("Используем реальные данные ETH с апреля по август 2025 года!")
    
    # Запускаем бэктест
    result = run_backtest(btc_df, eth_df, params)
    
    # Выводим результаты
    result.print_summary()
    
    # Показываем детали сделок
    print(f"\nДетали сделок:")
    for i, trade in enumerate(result.trades, 1):
        print(f"{i}. {trade['symbol']} {trade['side']}: "
              f"${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} "
              f"(PnL: ${trade['pnl']:.2f}, {trade['reason']})")


if __name__ == "__main__":
    main()
