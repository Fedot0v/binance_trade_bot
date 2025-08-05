class StrategyParameters:
    def __init__(self, raw: dict[str, str | float]):
        self.raw = raw or {}

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.raw.get(key, default))
        except (ValueError, TypeError):
            return default

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.raw.get(key, default))
        except (ValueError, TypeError):
            return default

    def as_dict(self) -> dict:
        return self.raw
