import csv


def parse_candles_csv(content: str):
    """
    Парсит CSV в список словарей [{timestamp, open, high, low, close, volume}, ...]
    Ожидает CSV с колонками: open_time, open, high, low, close, volume
    """
    candles = []
    reader = csv.DictReader(content.splitlines())
    for row in reader:
        candles.append({
            "timestamp": int(row["open_time"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return candles
