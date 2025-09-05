import pandas as pd
import requests
import tempfile
import os
from typing import Optional
from datetime import datetime, timedelta


class CSVDataService:
    """Сервис для работы с CSV данными"""
    
    @staticmethod
    def download_from_binance(symbol: str, start_date: str, end_date: str, interval: str = "1m") -> str:
        """
        Скачивает исторические данные с Binance API
        Возвращает путь к временному CSV файлу
        """
        # Конвертируем даты
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Binance API для исторических данных
        base_url = "https://api.binance.com/api/v3/klines"
        
        # Создаем временный файл
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        temp_file.write("timestamp,open,high,low,close,volume\n")
        
        current_date = start_dt
        while current_date <= end_dt:
            # Получаем данные по дням (максимум 1000 свечей за раз)
            params = {
                'symbol': symbol.upper(),
                'interval': interval,  # Используем интервал из шаблона
                'startTime': int(current_date.timestamp() * 1000),
                'endTime': int(min(current_date + timedelta(days=1), end_dt).timestamp() * 1000),
                'limit': 1000
            }
            
            try:
                response = requests.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                for candle in data:
                    timestamp = int(candle[0])
                    open_price = float(candle[1])
                    high_price = float(candle[2])
                    low_price = float(candle[3])
                    close_price = float(candle[4])
                    volume = float(candle[5])
                    
                    temp_file.write(f"{timestamp},{open_price},{high_price},{low_price},{close_price},{volume}\n")
                
                current_date += timedelta(days=1)
                
            except Exception as e:
                print(f"Ошибка при скачивании данных для {current_date}: {e}")
                current_date += timedelta(days=1)
                continue
        
        temp_file.close()
        return temp_file.name

    @staticmethod
    def download_dual_data_from_binance(symbol1: str, symbol2: str, start_date: str, end_date: str, interval: str = "1m") -> tuple[str, str]:
        """
        Скачивает исторические данные для двух символов с Binance API
        Возвращает кортеж путей к временным CSV файлам
        """
        file1 = CSVDataService.download_from_binance(symbol1, start_date, end_date, interval)
        file2 = CSVDataService.download_from_binance(symbol2, start_date, end_date, interval)
        return file1, file2
    
    @staticmethod
    def load_csv_data(file_path: str) -> pd.DataFrame:
        """Загружает и подготавливает CSV данные"""
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
            
            return df.sort_index()
            
        except Exception as e:
            raise ValueError(f"Ошибка загрузки CSV: {e}")
    
    @staticmethod
    def cleanup_temp_file(file_path: str) -> None:
        """Удаляет временный файл"""
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
