"""Tests: train→infer on synthetic labeled data + model versioning/reload."""

from __future__ import annotations

import random
import tempfile
from pathlib import Path

import pytest

from bot.learning.features import FEATURE_ORDER, extract_features
from bot.learning.model import (
    Scorer,
    Trainer,
    load_model,
    save_model,
)
from bot.scanner.models import TickerState
from bot.ta.models import MacdState


# ---------------------------------------------------------------------------
# Synthetic dataset helpers
# ---------------------------------------------------------------------------


def _make_ticker_state(
    rvol: float = 3.0,
    pct_change: float = 10.0,
    macd_eligible: bool = True,
    macd_favorability: float = 0.5,
    role: str = "leader",
    score: float = 70.0,
    pattern_tags: list[str] | None = None,
) -> TickerState:
    return TickerState(
        symbol="TEST",
        price=10.0,
        prev_close=9.0,
        gap_pct=pct_change,
        pct_change=pct_change,
        rvol=rvol,
        float_shares=5_000_000,
        unknown_float=False,
        tradable=True,
        has_news=True,
        macd_state=MacdState(
            value=0.2 if macd_eligible else -0.1,
            slope=0.05,
            hist=0.03,
            favorability=macd_favorability,
            eligible=macd_eligible,
        ),
        pattern_tags=pattern_tags or [],
        pattern_signature=[0.1] * 25,
        role=role,
        score=score,
    )


def _make_synthetic_dataset(
    n_good: int = 80,
    n_bad: int = 80,
    seed: int = 42,
) -> tuple[list[dict[str, float]], list[int]]:
    """Generate a linearly separable synthetic dataset.

    'Good' setups have high RVOL, high MACD favorability, and leader role.
    'Bad' setups have low RVOL, negative MACD, and laggard role.
    """
    rng = random.Random(seed)
    samples: list[dict[str, float]] = []
    labels: list[int] = []

    for _ in range(n_good):
        state = _make_ticker_state(
            rvol=rng.uniform(3.0, 8.0),
            pct_change=rng.uniform(8.0, 20.0),
            macd_eligible=True,
            macd_favorability=rng.uniform(0.4, 1.0),
            role="leader",
            score=rng.uniform(65.0, 95.0),
            pattern_tags=["bullish_engulfing"],
        )
        features = extract_features(
            state,
            sentiment_score=rng.uniform(0.3, 1.0),
            time_of_day_frac=rng.uniform(0.0, 0.5),
            sizing=rng.uniform(500.0, 2000.0),
        )
        samples.append(features)
        labels.append(1)

    for _ in range(n_bad):
        state = _make_ticker_state(
            rvol=rng.uniform(0.5, 1.5),
            pct_change=rng.uniform(-2.0, 3.0),
            macd_eligible=False,
            macd_favorability=rng.uniform(-1.0, -0.2),
            role="laggard",
            score=rng.uniform(10.0, 40.0),
            pattern_tags=[],
        )
        features = extract_features(
            state,
            sentiment_score=rng.uniform(-1.0, -0.1),
            time_of_day_frac=rng.uniform(0.5, 1.0),
            sizing=rng.uniform(50.0, 200.0),
        )
        samples.append(features)
        labels.append(0)

    return samples, labels


def _good_features() -> dict[str, float]:
    state = _make_ticker_state(
        rvol=6.0, macd_eligible=True, macd_favorability=0.9, role="leader", score=90.0
    )
    return extract_features(state, sentiment_score=0.8, time_of_day_frac=0.1, sizing=1000.0)


def _bad_features() -> dict[str, float]:
    state = _make_ticker_state(
        rvol=0.8, macd_eligible=False, macd_favorability=-0.7, role="laggard", score=15.0
    )
    return extract_features(state, sentiment_score=-0.6, time_of_day_frac=0.9, sizing=100.0)


# ---------------------------------------------------------------------------
# Trainer tests
# ---------------------------------------------------------------------------


class TestTrainer:
    def test_train_gradient_boosting_succeeds(self):
        samples, labels = _make_synthetic_dataset()
        trainer = Trainer(algorithm="gradient_boosting")
        mv = trainer.train(samples, labels)
        assert mv.version.startswith("v")
        assert mv.metrics.n_samples == len(samples)
        assert mv.metrics.algorithm == "gradient_boosting"

    def test_train_logistic_regression_succeeds(self):
        samples, labels = _make_synthetic_dataset(n_good=50, n_bad=50)
        trainer = Trainer(algorithm="logistic_regression")
        mv = trainer.train(samples, labels)
        assert mv.metrics.algorithm == "logistic_regression"

    def test_train_custom_version_string(self):
        samples, labels = _make_synthetic_dataset(n_good=20, n_bad=20)
        mv = Trainer().train(samples, labels, version="v_custom_42")
        assert mv.version == "v_custom_42"

    def test_train_metrics_populated(self):
        samples, labels = _make_synthetic_dataset()
        mv = Trainer().train(samples, labels)
        assert mv.metrics.n_positive == 80
        assert mv.metrics.n_negative == 80
        assert 0.0 <= mv.metrics.accuracy <= 1.0
        assert 0.0 <= mv.metrics.roc_auc <= 1.0
        assert mv.metrics.feature_count == len(FEATURE_ORDER)

    def test_train_accuracy_above_chance_on_separable_data(self):
        samples, labels = _make_synthetic_dataset()
        mv = Trainer().train(samples, labels)
        # A well-trained model on linearly-separable data should beat random
        assert mv.metrics.accuracy > 0.6

    def test_train_raises_on_too_few_samples(self):
        with pytest.raises(ValueError, match="at least 2"):
            Trainer().train([{"rvol": 1.0}], [1])

    def test_train_raises_on_single_class(self):
        samples, _ = _make_synthetic_dataset(n_good=5, n_bad=0)
        with pytest.raises(ValueError, match="both positive and negative"):
            Trainer().train(samples, [1] * 5)

    def test_train_raises_on_mismatched_lengths(self):
        samples, labels = _make_synthetic_dataset(n_good=10, n_bad=10)
        with pytest.raises(ValueError, match="same length"):
            Trainer().train(samples, labels[:-1])


# ---------------------------------------------------------------------------
# Scorer tests
# ---------------------------------------------------------------------------


class TestScorer:
    def test_score_setup_returns_probability_in_range(self):
        samples, labels = _make_synthetic_dataset()
        mv = Trainer().train(samples, labels)
        scorer = Scorer(mv)
        prob = scorer.score_setup(_good_features())
        assert 0.0 <= prob <= 1.0

    def test_score_setup_good_setup_higher_than_bad(self):
        samples, labels = _make_synthetic_dataset()
        mv = Trainer().train(samples, labels)
        scorer = Scorer(mv)
        assert scorer.score_setup(_good_features()) > scorer.score_setup(_bad_features())

    def test_scorer_version_matches_model_version(self):
        samples, labels = _make_synthetic_dataset(n_good=30, n_bad=30)
        mv = Trainer().train(samples, labels, version="v_test_999")
        scorer = Scorer(mv)
        assert scorer.version == "v_test_999"

    def test_score_setup_with_partial_features(self):
        samples, labels = _make_synthetic_dataset(n_good=30, n_bad=30)
        mv = Trainer().train(samples, labels)
        scorer = Scorer(mv)
        # Partial feature dict — missing keys default to 0.0
        partial: dict[str, float] = {"rvol": 5.0, "score": 80.0}
        prob = scorer.score_setup(partial)
        assert 0.0 <= prob <= 1.0


# ---------------------------------------------------------------------------
# Versioning / persistence tests
# ---------------------------------------------------------------------------


class TestModelPersistence:
    def test_save_and_reload_produces_same_predictions(self):
        samples, labels = _make_synthetic_dataset()
        mv = Trainer().train(samples, labels, version="v_persist_test")
        scorer_before = Scorer(mv)

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            save_model(mv, models_dir)

            mv_loaded = load_model("v_persist_test", models_dir)
            scorer_after = Scorer(mv_loaded)

            test_features = _good_features()
            assert scorer_before.score_setup(test_features) == pytest.approx(
                scorer_after.score_setup(test_features), abs=1e-9
            )

    def test_save_creates_joblib_and_meta_files(self):
        samples, labels = _make_synthetic_dataset(n_good=20, n_bad=20)
        mv = Trainer().train(samples, labels, version="v_files_check")

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            model_path = save_model(mv, models_dir)

            assert model_path.exists()
            assert (models_dir / "model_v_files_check_meta.json").exists()

    def test_load_restores_metrics(self):
        samples, labels = _make_synthetic_dataset()
        mv = Trainer().train(samples, labels, version="v_metrics_check")

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            save_model(mv, models_dir)
            mv_loaded = load_model("v_metrics_check", models_dir)

            assert mv_loaded.metrics.n_samples == mv.metrics.n_samples
            assert mv_loaded.metrics.accuracy == pytest.approx(mv.metrics.accuracy)
            assert mv_loaded.metrics.roc_auc == pytest.approx(mv.metrics.roc_auc)
            assert mv_loaded.version == mv.version

    def test_load_raises_if_model_file_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                load_model("v_nonexistent", Path(tmpdir))

    def test_multiple_versions_coexist(self):
        samples, labels = _make_synthetic_dataset(n_good=20, n_bad=20)

        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)
            mv1 = Trainer().train(samples, labels, version="v_001")
            mv2 = Trainer().train(samples, labels, version="v_002")
            save_model(mv1, models_dir)
            save_model(mv2, models_dir)

            loaded1 = load_model("v_001", models_dir)
            loaded2 = load_model("v_002", models_dir)
            assert loaded1.version == "v_001"
            assert loaded2.version == "v_002"
