from fastapi.testclient import TestClient
from main import app  # Импортируй своё FastAPI приложение


client = TestClient(app)


def test_trade_hub_unauth():
    resp = client.get("/trade/ui/hub/")
    assert resp.status_code in (302, 401)


# Пример для авторизованного пользователя:
# def test_trade_hub_auth(valid_token):
#     client.cookies.set("binauth", valid_token)
#     resp = client.get("/trade/ui/hub/")
#     assert resp.status_code == 200
