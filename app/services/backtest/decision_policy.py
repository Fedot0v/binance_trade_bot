from __future__ import annotations

from typing import Dict


def should_analyze_for_entry(open_positions: Dict, candle_index: int, is_compensation: bool = False) -> bool:
    # Для компенсационной стратегии: анализируем если нет позиций или есть только BTC позиция
    if is_compensation and len(open_positions) == 1:
        symbols = list(open_positions.keys())
        if len(symbols) == 1 and ('BTC' in symbols[0] or symbols[0].startswith('BTC')):
            if candle_index % 20 == 0:  # Каждые 20 свечей
                return True

    if open_positions:
        return False

    if candle_index % 20 == 0:
        return True

    return False


def should_analyze_compensation_entry(open_positions: Dict, md: Dict, btc_symbol: str, candle_index: int, parameters) -> bool:
    if len(open_positions) != 1:
        return False
    (sym, pos), = open_positions.items()
    if 'BTC' not in sym:
        return False

    try:
        threshold = float(parameters.get('compensation_threshold', 0.0025))
    except Exception:
        threshold = 0.0025

    if btc_symbol not in md:
        return False
    current_price = md[btc_symbol]['close'].iloc[-1]
    entry_price = pos['entry_price']
    side = pos['side']

    move = (current_price / entry_price) - 1.0
    against = (side == 'BUY' and move < 0) or (side == 'SELL' and move > 0)
    magnitude = abs(move)

    if against and magnitude >= threshold and (candle_index % 20 == 0):
        return True

    return False


def build_open_state(open_positions: Dict) -> Dict:
    """Создает open_state совместимый с тем что ожидают стратегии"""
    from types import SimpleNamespace
    
    open_state = {}
    for symbol, position in open_positions.items():
        # Создаем объект с атрибутами как у реальной сделки
        deal_obj = SimpleNamespace(
            id=position.get('deal_id'),
            symbol=symbol,
            entry_price=position.get('entry_price'),
            opened_at=position.get('entry_time'),
            side=position.get('side'),
            size=position.get('size'),
            leverage=position.get('leverage', 1),
            stop_loss=position.get('stop_loss'),
            take_profit=position.get('take_profit'),
            # Дополнительные поля для совместимости с реальными сделками
            position=position,
            # Добавляем поля которые может ожидать стратегия
            entry_size_usd=position.get('entry_size_usd'),
            max_price=position.get('max_price'),
            min_price=position.get('min_price'),
            trailing_stop=position.get('trailing_stop'),
        )
        open_state[symbol] = deal_obj
    
    return open_state


