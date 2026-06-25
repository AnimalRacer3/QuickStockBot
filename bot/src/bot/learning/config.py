from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LearningConfig:
    # Model persistence
    models_dir: Path = field(default_factory=lambda: Path("models"))
    algorithm: str = "gradient_boosting"  # or "logistic_regression"

    # Conviction gate (consumed by engine)
    conviction_threshold: float = 0.6

    # Daily efficiency tracking
    daily_profit_target_pct: float = 2.0
    daily_max_loss_pct: float = -2.0
    risk_per_trade_pct: float = 0.5
    min_hit_rate: float = 0.5
    efficiency_tuner_thresholds: list[float] = field(
        default_factory=lambda: [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    )

    @classmethod
    def from_env(cls) -> LearningConfig:
        def _float(key: str, default: float) -> float:
            return float(os.environ.get(key, default))

        def _str(key: str, default: str) -> str:
            return os.environ.get(key, default)

        return cls(
            models_dir=Path(os.environ.get("ML_MODELS_DIR", "models")),
            algorithm=_str("ML_ALGORITHM", "gradient_boosting"),
            conviction_threshold=_float("ML_CONVICTION_THRESHOLD", 0.6),
            daily_profit_target_pct=_float("DAILY_PROFIT_TARGET_PCT", 2.0),
            daily_max_loss_pct=_float("DAILY_MAX_LOSS_PCT", -2.0),
            risk_per_trade_pct=_float("RISK_PER_TRADE_PCT", 0.5),
            min_hit_rate=_float("ML_MIN_HIT_RATE", 0.5),
        )
