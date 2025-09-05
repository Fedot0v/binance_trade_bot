# Локальный запуск через Docker

## Быстрый старт

1. **Запуск приложения:**
   ```bash
   docker-compose -f docker-compose.local.yml up --build
   ```

2. **Открыть в браузере:**
   ```
   http://localhost:8000
   ```

## Что происходит

- PostgreSQL база данных на порту 5432
- Redis на порту 6379  
- FastAPI приложение на порту 8000
- Автоматическая инициализация БД
- Hot reload для разработки

## Остановка

```bash
docker-compose -f docker-compose.local.yml down
```

## Очистка данных

```bash
docker-compose -f docker-compose.local.yml down -v
```

## Особенности локальной версии

- Тестнет Binance API (BINANCE_TESTNET=true)
- Локальная база данных
- Отладочный режим
- Автоперезагрузка при изменении кода

## Переменные окружения

- `BINANCE_TESTNET=true` - использовать тестнет
- `BINANCE_API_URL` - основной API URL
- `BINANCE_TESTNET_URL` - URL тестнета
- `BINANCE_MAINNET_URL` - URL основной сети
