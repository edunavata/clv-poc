from datetime import datetime

import numpy as np
import pandas as pd

from dashboard.transforms import (
    book_stats_frame,
    bucket_hours,
    detect_gaps,
    heatmap_frame,
    sample_progress,
)


def test_book_stats_frame_adds_ci95():
    stats = pd.DataFrame(
        {
            "soft_book": ["bookA"],
            "n": [4],
            "avg_clv": [0.02],
            "std_clv": [0.04],
            "hit_rate": [0.5],
            "median_clv": [0.01],
        }
    )
    out = book_stats_frame(stats)
    # stderr = 0.04/sqrt(4) = 0.02; CI = 0.02 ± 1.96*0.02
    assert out["stderr"].iloc[0] == 0.02
    assert round(out["ci_low"].iloc[0], 4) == -0.0192
    assert round(out["ci_high"].iloc[0], 4) == 0.0592


def test_book_stats_frame_n1_gives_nan_ci():
    stats = pd.DataFrame(
        {
            "soft_book": ["bookA"],
            "n": [1],
            "avg_clv": [0.02],
            "std_clv": [np.nan],  # stddev_samp con n=1 es NULL en DuckDB
            "hit_rate": [1.0],
            "median_clv": [0.02],
        }
    )
    out = book_stats_frame(stats)
    assert np.isnan(out["ci_low"].iloc[0])


def test_bucket_hours_assigns_ordered_buckets():
    values = pd.DataFrame(
        {
            "soft_book": ["bookA"] * 4,
            "clv": [0.01, 0.03, -0.02, 0.05],
            "hours_to_commence": [0.5, 2.0, 2.5, 30.0],
        }
    )
    out = bucket_hours(values)
    by_bucket = out.set_index("bucket")
    assert by_bucket.loc["0-1h", "n"] == 1
    assert by_bucket.loc["1-3h", "n"] == 2
    assert round(by_bucket.loc["1-3h", "avg_clv"], 4) == 0.005
    assert by_bucket.loc["24h+", "n"] == 1


def test_detect_gaps_flags_only_holes_above_twice_interval():
    ts = pd.DataFrame(
        {
            "sport_key": ["s1"] * 4,
            "captured_at": pd.to_datetime(
                [
                    datetime(2026, 7, 1, 0, 0),
                    datetime(2026, 7, 1, 3, 0),  # 3h: normal
                    datetime(2026, 7, 1, 8, 0),  # 5h: <= 2x3h, no gap
                    datetime(2026, 7, 2, 0, 0),  # 16h: gap
                ]
            ),
        }
    )
    out = detect_gaps(ts, {"s1": 3.0})
    assert len(out) == 1
    assert out["gap_hours"].iloc[0] == 16.0
    assert out["gap_start"].iloc[0] == datetime(2026, 7, 1, 8, 0)


def test_detect_gaps_empty_when_no_gaps():
    ts = pd.DataFrame(
        {
            "sport_key": ["s1"],
            "captured_at": pd.to_datetime([datetime(2026, 7, 1)]),
        }
    )
    assert detect_gaps(ts, {"s1": 3.0}).empty


def test_heatmap_frame_fills_missing_days_with_zero():
    polls = pd.DataFrame(
        {
            "day": pd.to_datetime([datetime(2026, 7, 1), datetime(2026, 7, 3)]),
            "sport_key": ["s1", "s1"],
            "polls": [8, 4],
            "rows": [80, 40],
        }
    )
    out = heatmap_frame(polls, {"s1": 8.0})
    assert len(out) == 3  # 1, 2 y 3 de julio
    day2 = out[out["day"] == datetime(2026, 7, 2)].iloc[0]
    assert day2["polls"] == 0
    assert day2["ratio"] == 0.0
    assert out[out["day"] == datetime(2026, 7, 1)]["ratio"].iloc[0] == 1.0


def test_sample_progress_caps_at_100_pct():
    growth = pd.DataFrame({"day": [1, 2], "n_valid": [80, 60], "cumulative_n": [80, 140]})
    out = sample_progress(growth)
    assert out["n"] == 140
    assert out["pct"] == 1.0


def test_sample_progress_empty():
    assert sample_progress(pd.DataFrame())["n"] == 0
