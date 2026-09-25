"""
Tests on a hand-built panel where the right answer is known by construction.

Run: python -m pytest -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import config, rules


def _panel(rets, vols, ticker="TEST", start="2026-01-05"):
    """Build a clean OHLCV panel from daily returns and volumes."""
    n = len(rets)
    dates = pd.bdate_range(start=start, periods=n)
    close = 100 * np.cumprod(1 + np.asarray(rets, dtype=float))
    df = pd.DataFrame({
        "date": dates,
        "ticker": ticker,
        "open": close / (1 + np.asarray(rets) / 2),
        "high": close * 1.004,
        "low": close * 0.996,
        "close": close,
        "volume": np.asarray(vols, dtype=float),
    })
    # High and low must contain the move, so widen them on big days.
    df["high"] = np.maximum(df["high"], df[["open", "close"]].max(axis=1) * 1.002)
    df["low"] = np.minimum(df["low"], df[["open", "close"]].min(axis=1) * 0.998)
    return df


def _with_bench(df):
    bench = df[["date"]].drop_duplicates().assign(ticker="SPY", open=400.0, high=401.0,
                                                  low=399.0, close=400.0, volume=1e8)
    u = rules.add_indicators(df.copy())
    return rules.add_benchmark(u, bench)


def _setup(consolidation_rets, cons_vol=0.3, impulse_ret=0.09, impulse_vol=6.0):
    """25 quiet days, one impulse day, then the given consolidation days."""
    quiet_rets = [0.001, -0.001] * 13
    quiet_vols = [1_000_000] * 26
    rets = quiet_rets + [impulse_ret] + list(consolidation_rets)
    vols = quiet_vols + [1_000_000 * impulse_vol] + [1_000_000 * cons_vol] * len(consolidation_rets)
    df = _panel(rets, vols)
    df["volume"] = df["volume"] * 200  # clear the dollar-volume floor
    return _with_bench(df)


def test_impulse_day_is_flagged():
    u = _setup([0.002, -0.001])
    impulse_rows = u[u["is_impulse"]]
    assert len(impulse_rows) == 1
    assert impulse_rows["ret"].iloc[0] == pytest.approx(0.09, rel=1e-6)


def test_clean_consolidation_becomes_a_candidate():
    u = _setup([0.002, -0.001])
    cand = rules.build_candidates(u)
    assert len(cand) >= 1
    last = cand.iloc[-1]
    assert last["consolidation_days"] == 2
    assert last["gain_retained"] > 0.9          # barely gave anything back
    assert last["volume_fade"] < config.MAX_VOLUME_RATIO


def test_giving_the_move_back_is_rejected():
    # Two days that retrace ~80% of a 9% move: not a consolidation.
    u = _setup([-0.04, -0.035])
    cand = rules.build_candidates(u)
    assert cand.empty


def test_volume_that_never_fades_is_rejected():
    u = _setup([0.002, -0.001], cons_vol=7.0)   # consolidation busier than the impulse day
    cand = rules.build_candidates(u)
    assert cand.empty


def test_no_lookahead_truncating_the_future_changes_nothing():
    """Features on day T must be identical whether or not later rows exist."""
    u_full = _setup([0.002, -0.001, 0.001, 0.004, -0.02, 0.05])
    screen_date = u_full["date"].iloc[28]       # two days after the impulse

    full = rules.build_candidates(u_full)
    truncated = rules.build_candidates(u_full[u_full["date"] <= screen_date].copy())

    a = full[full["date"] == screen_date]
    b = truncated[truncated["date"] == screen_date]
    assert len(a) == 1 and len(b) == 1
    for col in ["lean_score", "gain_retained", "volume_fade", "range_contraction",
                "cons_high", "cons_low", "close"]:
        assert a[col].iloc[0] == pytest.approx(b[col].iloc[0], rel=1e-12)


def test_outcome_go_uses_the_next_session_only():
    u = _setup([0.002, -0.001, 0.06])           # day 3 breaks out hard
    cand = rules.build_candidates(u)
    scored = rules.add_outcomes(cand, u)
    row = scored[scored["consolidation_days"] == 2].iloc[0]
    assert row["outcome_go"] == (row["next_close"] > row["cons_high"])
    assert row["next_return"] == pytest.approx(row["next_close"] / row["close"] - 1, rel=1e-12)


def test_lean_score_is_bounded():
    u = _setup([0.002, -0.001, 0.001])
    cand = rules.build_candidates(u)
    assert cand["lean_score"].between(-1, 1).all()
