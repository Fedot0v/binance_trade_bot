import pandas as pd

from strategies.novichok_strategy import NovichokStrategy

# 1. Параметры стратегии
config = {
    "ema_fast": 7,
    "ema_slow": 21,
    "trend_threshold": 0.001,
    "risk_pct": 0.10,
    "stop_loss_pct": 0.015,
    "leverage": 10   # <-- Плечо
}

# 2. Данные
df = pd.read_csv("BTCUSDT-1m-2025-05.csv")
df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms")

strategy = NovichokStrategy(config)

balance = 3000  # Начальный депозит
signals = []
positions = []
position = None
entry_price = None
pnl_history = []
stop_loss_pct = config["stop_loss_pct"]
leverage = config.get("leverage", 1)
risk_pct = config["risk_pct"]

for i in range(len(df)):
    sub_df = df.iloc[:i+1]
    signal = strategy.generate_signal(sub_df)
    signals.append(signal)
    close_price = df["close"].iloc[i]

    # Открытие позиции
    if not position and signal in ("long", "short"):
        position = signal
        entry_price = close_price
        positions.append(position)
    # Переворот по встречному сигналу
    elif position and signal != position and signal in ("long", "short"):
        pnl = (close_price - entry_price) / entry_price if position == "long" else (entry_price - close_price) / entry_price
        profit = balance * risk_pct * pnl * leverage  # Профит в $
        pnl_history.append(profit)
        print(f"{df['timestamp'].iloc[i]} — {position.upper()} закрыта по сигналу {signal.upper()}, PnL: {profit:.2f} $")
        balance += profit
        position = signal
        entry_price = close_price
        positions.append(position)
    # Проверка стоп-лосса
    elif position:
        loss = (close_price - entry_price) / entry_price if position == "long" else (entry_price - close_price) / entry_price
        if loss < -stop_loss_pct:
            profit = balance * risk_pct * loss * leverage
            print(f"{df['timestamp'].iloc[i]} — {position.upper()} закрыта по стоп-лоссу, убыток: {profit:.2f} $")
            pnl_history.append(profit)
            balance += profit
            position = None
            entry_price = None
            positions.append("stop")

df["signal"] = signals

print("\nРезультат теста:")
print(f"Всего сделок: {len(pnl_history)}")
if pnl_history:
    print(f"Финальный депозит: {balance:.2f} $")
    print(f"Суммарная доходность: {100*(balance/3000-1):.2f}%")
    print(f"Средний PnL на сделку: {sum(pnl_history)/len(pnl_history):.2f} $")
else:
    print("Нет завершённых сделок.")

df.to_csv("btc_usdt_novichok_signals_leverage.csv", index=False)
