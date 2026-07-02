from datetime import date

from trader.config import Paths
from trader.journal import Journal


def _paths(tmp_path) -> Paths:
    return Paths(
        base_dir=tmp_path,
        journal_dir=tmp_path / "journal",
        logs_dir=tmp_path / "logs",
        replay_dir=tmp_path / "replay",
        performance_db=tmp_path / "performance_db.json",
        runs_csv=tmp_path / "runs.csv",
        reports_dir=tmp_path,
    )


def test_record_skip_dedupes_per_ticker_reason_with_count(tmp_path):
    journal = Journal(_paths(tmp_path), date(2026, 7, 2))

    for _ in range(5):
        journal.record_skip("DSY", "no_pattern")
    journal.record_skip("DSY", "below_vwap", details="pct=-0.50")
    journal.record_skip("CETX", "no_pattern")

    skips = journal._read_json_list(journal._skips_path())
    assert len(skips) == 3  # (DSY,no_pattern) (DSY,below_vwap) (CETX,no_pattern), not 7 rows

    dsy_no_pattern = next(s for s in skips if s["ticker"] == "DSY" and s["reason"] == "no_pattern")
    assert dsy_no_pattern["count"] == 5

    dsy_below_vwap = next(s for s in skips if s["ticker"] == "DSY" and s["reason"] == "below_vwap")
    assert dsy_below_vwap["count"] == 1
    assert dsy_below_vwap["details"] == "pct=-0.50"


def test_record_skip_updates_details_on_repeat(tmp_path):
    journal = Journal(_paths(tmp_path), date(2026, 7, 2))
    journal.record_skip("DSY", "rvol_low", details="rvol=1.00")
    journal.record_skip("DSY", "rvol_low", details="rvol=2.50")

    skips = journal._read_json_list(journal._skips_path())
    assert len(skips) == 1
    assert skips[0]["count"] == 2
    assert skips[0]["details"] == "rvol=2.50"


def test_skip_reason_counts_sums_deduped_counts(tmp_path):
    journal = Journal(_paths(tmp_path), date(2026, 7, 2))
    for _ in range(3):
        journal.record_skip("DSY", "no_pattern")
    for _ in range(2):
        journal.record_skip("CETX", "no_pattern")
    journal.record_skip("CETX", "below_vwap")

    counts = journal.skip_reason_counts()
    assert counts == {"no_pattern": 5, "below_vwap": 1}


def test_record_skip_survives_across_journal_instances(tmp_path):
    paths = _paths(tmp_path)
    Journal(paths, date(2026, 7, 2)).record_skip("DSY", "no_pattern")

    # A fresh Journal instance (e.g. a second run against the same day) must
    # still dedupe against what's already on disk, not start a duplicate row.
    second = Journal(paths, date(2026, 7, 2))
    second.record_skip("DSY", "no_pattern")

    skips = second._read_json_list(second._skips_path())
    assert len(skips) == 1
    assert skips[0]["count"] == 2
