def test_get_balance(mock_binance_client):
    balance = mock_binance_client.get_balance()
    assert balance == 1000


def test_place_order(mock_binance_client):
    result = mock_binance_client.place_order("BTCUSDT", "buy", 0.01)
    assert result["status"] == "filled"
