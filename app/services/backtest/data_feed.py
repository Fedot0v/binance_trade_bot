from __future__ import annotations

from typing import Dict, Iterator, Any
import pandas as pd


class DataFeed:
    """Поток рыночных данных для бэктеста.

    Предоставляет абстракцию итерации по свечам с формированием md-словаря и текущих цен.
    Не хранит бизнес-логику стратегий/закрытия — только доступ к данным.
    """

    def iter_single(self, data: pd.DataFrame, symbol: str, warmup: int = 0) -> Iterator[Dict[str, Any]]:
        start_index = max(0, warmup)
        for i in range(start_index, len(data)):
            current_time = data.index[i]
            current_slice = data.iloc[: i + 1]
            md = {symbol: current_slice}
            prices = {symbol: current_slice['close'].iloc[-1]}
            yield {
                'index': i,
                'time': current_time,
                'md': md,
                'prices': prices,
            }

    def iter_dual(
        self,
        data1: pd.DataFrame,
        data2: pd.DataFrame,
        symbol1: str,
        symbol2: str,
        warmup: int = 0,
    ) -> Iterator[Dict[str, Any]]:
        # Предполагается, что данные синхронизированы по времени заранее
        length = min(len(data1), len(data2))
        start_index = max(0, warmup)
        for i in range(start_index, length):
            current_time = data1.index[i]
            slice1 = data1.iloc[: i + 1]
            slice2 = data2.iloc[: i + 1]
            md = {symbol1: slice1, symbol2: slice2}
            prices = {
                symbol1: slice1['close'].iloc[-1],
                symbol2: slice2['close'].iloc[-1],
            }
            yield {
                'index': i,
                'time': current_time,
                'md': md,
                'prices': prices,
            }


