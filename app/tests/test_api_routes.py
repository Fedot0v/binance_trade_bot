# import pytest
# from unittest.mock import AsyncMock, MagicMock, patch
# from fastapi.testclient import TestClient
# from fastapi import HTTPException
# from uuid import uuid4

# from main import app
# from services.trade_service import TradeService
# from services.deal_service import DealService
# from schemas.deal import DealCreate, DealRead


# class TestAPIRoutes:
#     """Тесты для API роутов"""

#     @pytest.fixture
#     def client(self):
#         return TestClient(app)

#     @pytest.fixture
#     def sample_deal_data(self):
#         return {
#             "user_id": str(uuid4()),
#             "bot_id": 1,
#             "template_id": 1,
#             "symbol": "BTCUSDT",
#             "side": "long",
#             "entry_price": 50000.0,
#             "size": 0.001,
#             "stop_loss": 49000.0,
#             "status": "open"
#         }

#     @pytest.fixture
#     def sample_deal_response(self):
#         return {
#             "id": 1,
#             "user_id": str(uuid4()),
#             "bot_id": 1,
#             "template_id": 1,
#             "symbol": "BTCUSDT",
#             "side": "long",
#             "entry_price": 50000.0,
#             "size": 0.001,
#             "stop_loss": 49000.0,
#             "status": "open",
#             "opened_at": "2024-01-01T00:00:00",
#             "closed_at": None,
#             "pnl": None,
#             "exit_price": None
#         }

#     def test_health_endpoint(self, client):
#         """Тест эндпоинта здоровья"""
#         response = client.get("/health")
#         assert response.status_code == 200
#         assert response.json() == {"status": "ok"}

#     def test_create_deal_endpoint(self, client, sample_deal_data, sample_deal_response):
#         """Тест создания сделки через API"""
#         with patch('routes.deals_routers.DealService') as mock_deal_service_class:
#             mock_deal_service = AsyncMock()
#             mock_deal_service_class.return_value = mock_deal_service
            
#             # Мокаем создание сделки
#             mock_deal = MagicMock()
#             mock_deal.id = 1
#             mock_deal.user_id = sample_deal_data["user_id"]
#             mock_deal.symbol = sample_deal_data["symbol"]
#             mock_deal.side = sample_deal_data["side"]
#             mock_deal.entry_price = sample_deal_data["entry_price"]
#             mock_deal.size = sample_deal_data["size"]
#             mock_deal.stop_loss = sample_deal_data["stop_loss"]
#             mock_deal.status = sample_deal_data["status"]
#             mock_deal.opened_at = "2024-01-01T00:00:00"
#             mock_deal.closed_at = None
#             mock_deal.pnl = None
#             mock_deal.exit_price = None
            
#             mock_deal_service.create.return_value = mock_deal
            
#             # Отправляем запрос
#             response = client.post("/deals/", json=sample_deal_data)
            
#             # Проверяем ответ
#             assert response.status_code == 201  # 201 Created
#             data = response.json()
#             assert data["id"] == 1
#             assert data["symbol"] == "BTCUSDT"
#             assert data["side"] == "long"

#     def test_get_deals_endpoint(self, client, sample_deal_response):
#         """Тест получения списка сделок через API"""
#         with patch('routes.deals_routers.DealService') as mock_deal_service_class:
#             mock_deal_service = AsyncMock()
#             mock_deal_service_class.return_value = mock_deal_service
            
#             # Мокаем получение сделок
#             mock_deal = MagicMock()
#             mock_deal.id = 1
#             mock_deal.user_id = str(uuid4())
#             mock_deal.symbol = "BTCUSDT"
#             mock_deal.side = "long"
#             mock_deal.entry_price = 50000.0
#             mock_deal.size = 0.001
#             mock_deal.stop_loss = 49000.0
#             mock_deal.status = "open"
#             mock_deal.opened_at = "2024-01-01T00:00:00"
#             mock_deal.closed_at = None
#             mock_deal.pnl = None
#             mock_deal.exit_price = None
            
#             mock_deal_service.get_all.return_value = [mock_deal]
            
#             # Отправляем запрос
#             response = client.get("/deals/")
            
#             # Проверяем ответ
#             assert response.status_code == 200
#             data = response.json()
#             assert len(data) == 1
#             assert data[0]["id"] == 1
#             assert data[0]["symbol"] == "BTCUSDT"

#     def test_get_deal_by_id_endpoint(self, client, sample_deal_response):
#         """Тест получения сделки по ID через API"""
#         with patch('routes.deals_routers.DealService') as mock_deal_service_class:
#             mock_deal_service = AsyncMock()
#             mock_deal_service_class.return_value = mock_deal_service
            
#             # Мокаем получение сделки
#             mock_deal = MagicMock()
#             mock_deal.id = 1
#             mock_deal.user_id = str(uuid4())
#             mock_deal.symbol = "BTCUSDT"
#             mock_deal.side = "long"
#             mock_deal.entry_price = 50000.0
#             mock_deal.size = 0.001
#             mock_deal.stop_loss = 49000.0
#             mock_deal.status = "open"
#             mock_deal.opened_at = "2024-01-01T00:00:00"
#             mock_deal.closed_at = None
#             mock_deal.pnl = None
#             mock_deal.exit_price = None
            
#             mock_deal_service.get_by_id.return_value = mock_deal
            
#             # Отправляем запрос
#             response = client.get("/deals/1")
            
#             # Проверяем ответ
#             assert response.status_code == 200
#             data = response.json()
#             assert data["id"] == 1
#             assert data["symbol"] == "BTCUSDT"

#     def test_get_deal_by_id_not_found(self, client):
#         """Тест получения несуществующей сделки по ID"""
#         with patch('routes.deals_routers.DealService') as mock_deal_service_class:
#             mock_deal_service = AsyncMock()
#             mock_deal_service_class.return_value = mock_deal_service
            
#             # Мокаем ошибку 404
#             mock_deal_service.get_by_id.side_effect = HTTPException(
#                 status_code=404, detail="Сделка с ID 999 не найдена"
#             )
            
#             # Отправляем запрос
#             response = client.get("/deals/999")
            
#             # Проверяем ответ
#             assert response.status_code == 404
#             data = response.json()
#             assert "не найдена" in data["detail"]

#     def test_delete_deal_endpoint(self, client):
#         """Тест удаления сделки через API"""
#         with patch('routes.deals_routers.DealService') as mock_deal_service_class:
#             mock_deal_service = AsyncMock()
#             mock_deal_service_class.return_value = mock_deal_service
            
#             # Мокаем удаление сделки
#             mock_deal_service.delete_by_id.return_value = {
#                 "id": 1,
#                 "message": "Сделка успешно удалена"
#             }
            
#             # Отправляем запрос
#             response = client.delete("/deals/1")
            
#             # Проверяем ответ
#             assert response.status_code == 200
#             data = response.json()
#             assert data["id"] == 1
#             assert "успешно удалена" in data["message"]

#     def test_start_trading_endpoint(self, client):
#         """Тест запуска торговли через API"""
#         with patch('routes.trade_router.TradeService') as mock_trade_service_class:
#             mock_trade_service = AsyncMock()
#             mock_trade_service_class.return_value = mock_trade_service
            
#             # Мокаем запуск торговли
#             mock_trade_service.start_trading.return_value = {"status": "started"}
            
#             # Отправляем запрос
#             response = client.post("/trade/start", json={
#                 "user_id": str(uuid4()),
#                 "test_mode": True
#             })
            
#             # Проверяем ответ
#             assert response.status_code == 200
#             data = response.json()
#             assert data["status"] == "started"

#     def test_stop_trading_endpoint(self, client):
#         """Тест остановки торговли через API"""
#         with patch('routes.trade_router.TradeService') as mock_trade_service_class:
#             mock_trade_service = AsyncMock()
#             mock_trade_service_class.return_value = mock_trade_service
            
#             # Мокаем остановку торговли
#             mock_trade_service.stop_trading.return_value = {"status": "stopped"}
            
#             # Отправляем запрос
#             response = client.post("/trade/stop", json={
#                 "user_id": str(uuid4())
#             })
            
#             # Проверяем ответ
#             assert response.status_code == 200
#             data = response.json()
#             assert data["status"] == "stopped"

#     def test_get_bot_status_endpoint(self, client):
#         """Тест получения статуса бота через API"""
#         with patch('routes.trade_router.TradeService') as mock_trade_service_class:
#             mock_trade_service = AsyncMock()
#             mock_trade_service_class.return_value = mock_trade_service
            
#             # Мокаем получение статуса
#             mock_trade_service.get_bot_status.return_value = "running"
            
#             # Отправляем запрос
#             response = client.get("/trade/status/test-user-123")
            
#             # Проверяем ответ
#             assert response.status_code == 200
#             data = response.json()
#             assert data["status"] == "running"

#     def test_get_logs_endpoint(self, client):
#         """Тест получения логов через API"""
#         with patch('routes.trade_router.TradeService') as mock_trade_service_class:
#             mock_trade_service = AsyncMock()
#             mock_trade_service_class.return_value = mock_trade_service
            
#             # Мокаем получение логов
#             mock_trade_service.get_logs.return_value = [
#                 {"id": 1, "message": "Test log message", "timestamp": "2024-01-01T00:00:00"}
#             ]
            
#             # Отправляем запрос
#             response = client.get("/trade/logs/1")
            
#             # Проверяем ответ
#             assert response.status_code == 200
#             data = response.json()
#             assert len(data) == 1
#             assert data[0]["id"] == 1
#             assert "Test log message" in data[0]["message"]

#     def test_invalid_json_request(self, client):
#         """Тест обработки некорректного JSON в запросе"""
#         # Отправляем некорректный JSON
#         response = client.post("/deals/", data="invalid json")
        
#         # Проверяем, что возвращается ошибка 422
#         assert response.status_code == 422

#     def test_missing_required_fields(self, client):
#         """Тест обработки запроса с отсутствующими обязательными полями"""
#         # Отправляем данные без обязательных полей
#         incomplete_data = {
#             "symbol": "BTCUSDT"
#             # Отсутствуют user_id, bot_id и другие обязательные поля
#         }
        
#         response = client.post("/deals/", json=incomplete_data)
        
#         # Проверяем, что возвращается ошибка валидации
#         assert response.status_code == 422

#     def test_server_error_handling(self, client, sample_deal_data):
#         """Тест обработки серверных ошибок"""
#         with patch('routes.deals_routers.DealService') as mock_deal_service_class:
#             mock_deal_service = AsyncMock()
#             mock_deal_service_class.return_value = mock_deal_service
            
#             # Мокаем серверную ошибку
#             mock_deal_service.create.side_effect = Exception("Database connection error")
            
#             # Отправляем запрос
#             response = client.post("/deals/", json=sample_deal_data)
            
#             # Проверяем, что возвращается ошибка 500
#             assert response.status_code == 500

#     def test_cors_headers(self, client):
#         """Тест CORS заголовков"""
#         response = client.options("/deals/")
        
#         # Проверяем наличие CORS заголовков
#         assert "access-control-allow-origin" in response.headers
#         assert "access-control-allow-methods" in response.headers

#     def test_api_documentation_endpoints(self, client):
#         """Тест эндпоинтов документации API"""
#         # Проверяем Swagger UI
#         response = client.get("/docs")
#         assert response.status_code == 200
        
#         # Проверяем OpenAPI schema
#         response = client.get("/openapi.json")
#         assert response.status_code == 200
#         data = response.json()
#         assert "openapi" in data
#         assert "paths" in data 