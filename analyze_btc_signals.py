import pandas as pd
import numpy as np

def analyze_btc_signals():
    # Загружаем данные последних 2 месяцев
    df = pd.read_csv('BTCUSDT-1m-last-2-months.csv')
    df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.set_index('open_time').sort_index()

    # Берем последние 3 недели
    end_date = df.index.max()
    start_date = end_date - pd.Timedelta(weeks=3)
    df_3w = df[df.index >= start_date]

    print(f'Период: {start_date} - {end_date}')
    print(f'Количество свечей: {len(df_3w)}')

    # Рассчитываем EMA с вашими параметрами
    ema_fast = df_3w['close'].ewm(span=5).mean()
    ema_slow = df_3w['close'].ewm(span=21).mean()

    # Рассчитываем разницу в процентах
    diff_pct = abs(ema_fast - ema_slow) / ema_slow * 100

    print("\nАнализ разницы EMA:")
    print(f'Средняя разница: {diff_pct.mean():.4f}%')
    print(f'Медианная разница: {diff_pct.median():.4f}%')
    print(f'Максимальная разница: {diff_pct.max():.4f}%')
    print(f'Минимальная разница: {diff_pct.min():.4f}%')

    # Ваш порог trend_threshold = 0.0005 = 0.05%
    threshold = 0.05
    signals_above_threshold = (diff_pct > threshold).sum()
    total_candles = len(diff_pct)

    print(f'\nПорог trend_threshold: {threshold}%')
    print(f'Количество свечей выше порога: {signals_above_threshold}')
    print(f'Общее количество свечей: {total_candles}')
    print(f'Процент свечей с потенциальными сигналами: {(signals_above_threshold/total_candles)*100:.2f}%')

    # Анализируем волатильность
    returns = df_3w['close'].pct_change()
    volatility = returns.std() * np.sqrt(1440) * 100  # дневная волатильность
    print(f'\nДневная волатильность: {volatility:.2f}%')

    # Проверяем, пересекаются ли EMA
    cross_signals = []
    prev_diff = None

    for i in range(1, len(ema_fast)):
        current_diff = ema_fast.iloc[i] - ema_slow.iloc[i]
        if prev_diff is not None:
            if prev_diff <= 0 and current_diff > 0:
                cross_signals.append(('long', df_3w.index[i]))
            elif prev_diff >= 0 and current_diff < 0:
                cross_signals.append(('short', df_3w.index[i]))
        prev_diff = current_diff

    print(f'\nКоличество пересечений EMA: {len(cross_signals)}')
    for signal_type, timestamp in cross_signals[-5:]:  # последние 5
        print(f'{signal_type.upper()}: {timestamp}')

if __name__ == "__main__":
    analyze_btc_signals()
