from dataclasses import dataclass
from typing import Literal, Optional, Protocol, Dict, Any, List
import pandas as pd


Side = Literal["BUY", "SELL"]
Role = Literal["primary", "hedge"]
Sizing = Literal["usd", "risk_pct", "qty"]

MarketData = Dict[str, pd.DataFrame]
OpenState = Dict[str, Any]



@dataclass(frozen=True)
class OrderIntent:
    """Represents an intent of future action on the market."""
    symbol: str
    side: Side
    sizing: Sizing = "usd"
    size: float = 0.0
    role: Role = "primary"
    
    def validate(self) -> None:
        if not self.symbol or not isinstance(self.symbol, str):
            raise ValueError("OrderIntent.symbol must be non-empty string")
        if self.side not in ("BUY", "SELL"):
            raise ValueError("OrderIntent.side must be BUY or SELL")
        if self.size <= 0:
            raise ValueError("OrderIntent.size must be > 0")
        if self.role not in ("primary", "hedge"):
            raise ValueError("OrderIntent.role must be 'primary' or 'hedge'")


@dataclass(frozen=True)
class Decision:
    """
    Decision of the strategy to execute in one tick.
    If `intens` is empty, it means no action is needed.
    """
    intents: list[OrderIntent]
    bundle_ttl_sec: Optional[int] = None

    def is_empty(self) -> bool:
        return not self.intents

    def validate(self) -> None:
        for it in self.intents:
            it.validate()

        seen = set()
        for it in self.intents:
            key = (it.symbol, it.side)
            if key in seen:
                raise ValueError(f"Duplicate intent for {key} in one Decision")
            seen.add(key)


class Strategy(Protocol):
    """Contract, that all strategies must implement."""
    id: str
    
    def required_symbols(self, template) -> List[str]:
        """Which symbols must be downloaded for decision making."""
        pass
    
    async def decide(
        self,
        md: MarketData,
        template,
        open_state: OpenState
    ) -> Decision:
        """Return Decision: list of intents to execute."""
        pass
