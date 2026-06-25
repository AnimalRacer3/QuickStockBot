"""Supervised classifier over momentum features with model versioning."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

from bot.learning.features import FEATURE_ORDER, features_to_vector

Algorithm = Literal["gradient_boosting", "logistic_regression"]


@dataclass
class TrainingMetrics:
    n_samples: int
    n_positive: int
    n_negative: int
    accuracy: float
    roc_auc: float
    algorithm: str
    feature_count: int


@dataclass
class ModelVersion:
    """A trained, versioned model."""

    version: str          # e.g. "v1717200000"
    model: Any            # sklearn estimator
    metrics: TrainingMetrics
    trained_at: int       # unix timestamp


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


class Trainer:
    """Trains a binary classifier on labeled feature dicts."""

    def __init__(self, algorithm: Algorithm = "gradient_boosting") -> None:
        self.algorithm = algorithm

    def train(
        self,
        samples: list[dict[str, float]],
        labels: list[int],
        *,
        version: str | None = None,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> ModelVersion:
        """Train and return a versioned model.

        Args:
            samples: Feature dicts produced by ``extract_features``.
            labels: Binary labels (1 = good, 0 = bad).
            version: Override the auto-generated version string.
            test_size: Fraction held out for evaluation metrics.
            random_state: RNG seed for reproducibility.

        Raises:
            ValueError: Fewer than 2 samples or only one class present.
        """
        if len(samples) < 2:
            raise ValueError(f"Need at least 2 samples, got {len(samples)}")
        if len(set(labels)) < 2:
            raise ValueError("Need both positive and negative labels to train")
        if len(samples) != len(labels):
            raise ValueError("samples and labels must have the same length")

        x_mat = np.array([features_to_vector(s) for s in samples], dtype=np.float64)
        y = np.array(labels, dtype=np.int32)

        estimator = self._build_estimator(random_state)

        # Split only when we have enough data for a meaningful eval set
        if len(samples) >= 10:
            x_train, x_test, y_train, y_test = train_test_split(
                x_mat, y, test_size=test_size, random_state=random_state, stratify=y
            )
        else:
            x_train, x_test, y_train, y_test = x_mat, x_mat, y, y

        estimator.fit(x_train, y_train)

        y_prob = estimator.predict_proba(x_test)[:, 1]
        y_pred = (y_prob >= 0.5).astype(np.int32)

        try:
            roc = float(roc_auc_score(y_test, y_prob))
        except ValueError:
            roc = 0.5  # single class in test split

        metrics = TrainingMetrics(
            n_samples=len(samples),
            n_positive=int(np.sum(y)),
            n_negative=int(len(y) - np.sum(y)),
            accuracy=float(accuracy_score(y_test, y_pred)),
            roc_auc=roc,
            algorithm=self.algorithm,
            feature_count=len(FEATURE_ORDER),
        )

        ver = version or f"v{int(time.time())}"
        return ModelVersion(
            version=ver,
            model=estimator,
            metrics=metrics,
            trained_at=int(time.time()),
        )

    def _build_estimator(self, random_state: int) -> Any:
        if self.algorithm == "logistic_regression":
            return LogisticRegression(
                max_iter=1000, random_state=random_state, solver="lbfgs"
            )
        return GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=3,
            random_state=random_state,
        )


# ---------------------------------------------------------------------------
# Scoring / inference
# ---------------------------------------------------------------------------


class Scorer:
    """Scores a feature dict using a trained ModelVersion."""

    def __init__(self, mv: ModelVersion) -> None:
        self._mv = mv

    @property
    def version(self) -> str:
        return self._mv.version

    def score_setup(self, features: dict[str, float]) -> float:
        """Return the probability [0, 1] that the setup is a good (profitable) trade.

        Consumed by the engine's conviction gate:
            if scorer.score_setup(features) >= conviction_threshold: enter trade.
        """
        vec = np.array([features_to_vector(features)], dtype=np.float64)
        prob: float = float(self._mv.model.predict_proba(vec)[0, 1])
        return prob


# ---------------------------------------------------------------------------
# Persistence (versioned files)
# ---------------------------------------------------------------------------


def save_model(mv: ModelVersion, models_dir: Path) -> Path:
    """Persist a ModelVersion to *models_dir*.

    Creates two files:
    - ``model_{version}.joblib`` — serialised sklearn estimator.
    - ``model_{version}_meta.json`` — metrics and metadata.

    Returns the path to the joblib file.
    """
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / f"model_{mv.version}.joblib"
    meta_path = models_dir / f"model_{mv.version}_meta.json"

    joblib.dump(mv.model, model_path)

    meta: dict[str, Any] = {
        "version": mv.version,
        "trained_at": mv.trained_at,
        "algorithm": mv.metrics.algorithm,
        "n_samples": mv.metrics.n_samples,
        "n_positive": mv.metrics.n_positive,
        "n_negative": mv.metrics.n_negative,
        "accuracy": mv.metrics.accuracy,
        "roc_auc": mv.metrics.roc_auc,
        "feature_count": mv.metrics.feature_count,
        "feature_order": list(FEATURE_ORDER),
    }
    meta_path.write_text(json.dumps(meta, indent=2))

    return model_path


def load_model(version: str, models_dir: Path) -> ModelVersion:
    """Load a previously saved ModelVersion from *models_dir*.

    Raises:
        FileNotFoundError: If the version files are missing.
    """
    model_path = models_dir / f"model_{version}.joblib"
    meta_path = models_dir / f"model_{version}_meta.json"

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not meta_path.exists():
        raise FileNotFoundError(f"Model metadata not found: {meta_path}")

    estimator = joblib.load(model_path)
    meta = json.loads(meta_path.read_text())

    metrics = TrainingMetrics(
        n_samples=meta["n_samples"],
        n_positive=meta["n_positive"],
        n_negative=meta["n_negative"],
        accuracy=meta["accuracy"],
        roc_auc=meta["roc_auc"],
        algorithm=meta["algorithm"],
        feature_count=meta["feature_count"],
    )

    return ModelVersion(
        version=meta["version"],
        model=estimator,
        metrics=metrics,
        trained_at=meta["trained_at"],
    )
