import pandas as pd
import requests
import tempfile
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path


class CSVLoaderService:
    """Сервис для загрузки и управления CSV данными для бектеста"""
    
    def __init__(self):
        self.temp_files: List[str] = []
    
    def download_from_binance(
        self, 
        symbol: str, 
        start_date: str, 
        end_date: str, 
        interval: str = "1m"
    ) -> str:
        """
        Скачивает исторические данные с Binance API
        
        Args:
            symbol: Торговая пара (например, BTCUSDT)
            start_date: Дата начала в формате YYYY-MM-DD
            end_date: Дата окончания в формате YYYY-MM-DD
            interval: Интервал свечей (1m, 5m, 15m, 1h, 4h, 1d)
            
        Returns:
            str: Путь к временному CSV файлу
        """
        # Конвертируем даты
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        if start_dt > end_dt:
            raise ValueError("Дата начала должна быть раньше даты окончания")
        
        # Binance API для исторических данных
        base_url = "https://api.binance.com/api/v3/klines"
        
        # Создаем временный файл
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write("timestamp,open,high,low,close,volume\n")
        
        # Диапазон времени в миллисекундах: включительно по дате окончания (до конца дня)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms_inclusive = int((end_dt + timedelta(days=1)).timestamp() * 1000) - 1

        cursor_ms = start_ms
        total_candles = 0
        
        print(f"📥 Скачивание данных для {symbol} с {start_date} по {end_date}")
        
        # Пагинация запросов по 1000 свечей
        day_candle_counter = 0
        current_day = datetime.fromtimestamp(cursor_ms / 1000.0).date()
        try:
            while cursor_ms <= end_ms_inclusive:
                params = {
                    'symbol': symbol.upper(),
                    'interval': interval,
                    'startTime': cursor_ms,
                    'endTime': end_ms_inclusive,
                    'limit': 1000,
                }
                response = requests.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError(f"Unexpected response: {data}")

                if not data:
                    # Нет данных — выходим
                    break

                for candle in data:
                    ts = int(candle[0])
                    open_price = float(candle[1])
                    high_price = float(candle[2])
                    low_price = float(candle[3])
                    close_price = float(candle[4])
                    volume = float(candle[5])

                    # Записываем только в пределах диапазона
                    if ts < start_ms or ts > end_ms_inclusive:
                        continue
                    temp_file.write(f"{ts},{open_price},{high_price},{low_price},{close_price},{volume}\n")
                    total_candles += 1
                    day = datetime.fromtimestamp(ts / 1000.0).date()
                    if day != current_day:
                        # Выводим счетчик за предыдущий день
                        print(f"  ✅ {current_day.isoformat()}: {day_candle_counter} свечей")
                        current_day = day
                        day_candle_counter = 0
                    day_candle_counter += 1

                # Следующий курсор — следующий миллисекунд после последней свечи
                last_ts = int(data[-1][0])
                if last_ts == cursor_ms:
                    # Предохранитель от зацикливания
                    cursor_ms += 1
                else:
                    cursor_ms = last_ts + 1
        except Exception as e:
            print(f"  ❌ Ошибка при скачивании данных: {e}")
        
        temp_file.close()
        self.temp_files.append(temp_file.name)
        
        print(f"✅ Всего скачано {total_candles} свечей в файл: {temp_file.name}")
        return temp_file.name

    def download_dual_from_binance(
        self,
        symbol1: str,
        symbol2: str,
        start_date: str,
        end_date: str,
        interval: str = "1m"
    ) -> tuple[str, str]:
        """Скачивает данные для двух символов и возвращает пути к файлам."""
        file1 = self.download_from_binance(symbol1, start_date, end_date, interval)
        file2 = self.download_from_binance(symbol2, start_date, end_date, interval)
        return file1, file2
    
    def load_csv_data(self, file_path: str) -> pd.DataFrame:
        """
        Загружает и подготавливает CSV данные для бектеста
        
        Args:
            file_path: Путь к CSV файлу
            
        Returns:
            pd.DataFrame: Подготовленные данные
        """
        try:
            df = pd.read_csv(file_path)
            
            # Конвертируем timestamp
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                raise ValueError(f"Отсутствуют колонки: {missing_cols}")
            
            # Конвертируем числовые колонки в float
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Удаляем строки с NaN значениями
            df = df.dropna()
            
            # Сортируем по времени
            df = df.sort_index()
            
            # Проверяем, что данные не пустые
            if df.empty:
                raise ValueError("CSV файл не содержит данных")
            
            print(f"📊 Загружено {len(df)} свечей с {df.index[0]} по {df.index[-1]}")
            
            return df
            
        except Exception as e:
            raise ValueError(f"Ошибка при загрузке CSV файла: {e}")
    
    def validate_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Проверяет качество данных для бектеста
        
        Args:
            df: DataFrame с данными
            
        Returns:
            Dict: Результаты проверки качества
        """
        quality_report = {
            'total_candles': len(df),
            'date_range': {
                'start': df.index[0].strftime('%Y-%m-%d %H:%M:%S'),
                'end': df.index[-1].strftime('%Y-%m-%d %H:%M:%S')
            },
            'missing_values': df.isnull().sum().to_dict(),
            'duplicates': df.index.duplicated().sum(),
            'price_anomalies': 0,
            'volume_anomalies': 0
        }
        
        # Проверяем аномалии в ценах
        for col in ['open', 'high', 'low', 'close']:
            if col in df.columns:
                # Проверяем на отрицательные цены
                negative_prices = (df[col] <= 0).sum()
                quality_report['price_anomalies'] += negative_prices
                
                # Проверяем на экстремально высокие цены (> 1M)
                extreme_prices = (df[col] > 1000000).sum()
                quality_report['price_anomalies'] += extreme_prices
        
        # Проверяем аномалии в объеме
        if 'volume' in df.columns:
            quality_report['volume_anomalies'] = (df['volume'] < 0).sum()
        
        return quality_report
    
    def cleanup_temp_files(self):
        """Удаляет все временные файлы"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    print(f"🗑️ Удален временный файл: {temp_file}")
            except Exception as e:
                print(f"❌ Ошибка при удалении {temp_file}: {e}")
        
        self.temp_files.clear()

    def cleanup_temp_file(self, file_path: str) -> None:
        """Удаляет указанный временный файл, если он существует."""
        try:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)
                if file_path in self.temp_files:
                    self.temp_files.remove(file_path)
                print(f"🗑️ Удален временный файл: {file_path}")
        except Exception as e:
            print(f"❌ Ошибка при удалении {file_path}: {e}")
    
    def __del__(self):
        """Деструктор для автоматической очистки временных файлов"""
        self.cleanup_temp_files()
