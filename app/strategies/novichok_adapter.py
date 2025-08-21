from typing import Dict, List, Any

import pandas as pd

from strategies.contracts import Decision, OrderIntent


def _sym_str(x) -> str:
    return x.value if hasattr(x, "value") else str(x)


class NovichokAdapter:
    """
    Wrapper for Novichok strategy
    """

    id = "novichok-adapter"

    def __init__(self, legacy_novichok):
        self.legacy = legacy_novichok

    def required_symbols(self, template) -> List[str]:
        return [_sym_str(getattr(template, "symbol", "BTCUSDT"))]

    async def decide(
        self,
        md: Dict[str, pd.DataFrame],
        template,
        open_state: Dict[str, Any] | None = None
    ) -> Decision:
        symbol = self.required_symbols(template)[0]
        df = md.get(symbol)
        if df is None or df.empty:
            return Decision(intents=[])

        signal = self.legacy.generate_signal(df)
        if signal == "hold":
            return Decision(intents=[])

        side = "BUY" if signal == "long" else "SELL"

        risk_pct = float(getattr(
            template,
            "deposit_prct", 
            getattr(self.legacy, "deposit_prct", 0.01)  # дефолт в долях
            )
        )

        intent = OrderIntent(
            symbol=symbol,
            side=side,
            sizing="risk_pct",
            size=risk_pct,
            role="primary"
        )
        return Decision(intents=[intent])
