from __future__ import annotations

from typing import Tuple
import pandas as pd


class MarketDataUtils:
    """Утилиты для работы с историческими данными (синхронизация, обрезка диапазонов)."""

    @staticmethod
    def synchronize_two(df1: pd.DataFrame, df2: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Синхронизирует два набора данных по общему индексу времени.

        - Вычисляет пересечение таймстампов
        - Реиндексирует оба датафрейма на общий индекс
        - Заполняет пропуски forward-fill, затем удаляет оставшиеся NaN
        """
        common_index = df1.index.intersection(df2.index)
        if common_index.empty:
            return df1.iloc[0:0], df2.iloc[0:0]

        df1_sync = df1.reindex(common_index).ffill().dropna()
        df2_sync = df2.reindex(common_index).ffill().dropna()
        # Приводим к одному набору индексов после dropna
        final_index = df1_sync.index.intersection(df2_sync.index)
        return df1_sync.loc[final_index], df2_sync.loc[final_index]

    @staticmethod
    def synchronize_pair(btc_data: pd.DataFrame, eth_data: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        return MarketDataUtils.synchronize_two(btc_data, eth_data)


