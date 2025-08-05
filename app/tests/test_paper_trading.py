from uuid import uuid4


# Можешь использовать фикстуру fake_user_id, если хочешь
class PaperTradeService:
    def __init__(self):
        self.deals = {}

    def open_deal(self, user_id, params):
        deal_id = uuid4()
        self.deals[deal_id] = {"user_id": user_id, "params": params, "status": "open"}
        return deal_id

    def close_deal(self, deal_id):
        if deal_id in self.deals:
            self.deals[deal_id]["status"] = "closed"
            return True
        return False

def test_paper_trading_cycle(fake_user_id, sample_strategy_params):
    service = PaperTradeService()
    deal_id = service.open_deal(fake_user_id, sample_strategy_params)
    assert service.deals[deal_id]["status"] == "open"
    closed = service.close_deal(deal_id)
    assert closed
    assert service.deals[deal_id]["status"] == "closed"
