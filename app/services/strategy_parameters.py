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

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.raw.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("true", "1", "yes", "y", "on"):  # truthy strings
                return True
            if s in ("false", "0", "no", "n", "off"):  # falsy strings
                return False
            return default
        return bool(value)

    def get_str(self, key: str, default: str = "") -> str:
        value = self.raw.get(key, default)
        return str(value) if value is not None else default

    def as_dict(self) -> dict:
        return self.raw
