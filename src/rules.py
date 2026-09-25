from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


# ---------------------------------------------------------------------------
# Per-ticker indicators
# ---------------------------------------------------------------------------

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add returns, trailing vol, trailing volume and true range, per ticker.

    Trailing statistics are shifted by one day so that a day is never judged against a
    window that includes itself.
    """
    df = df.sort_values(["ticker", "date"]).copy()
    g = df.groupby("ticker", sort=False)

    df["ret"] = g["close"].pct_change()
    df["prev_close"] = g["close"].shift(1)

    logret = np.log(df["close"] / df["prev_close"])
    df["sigma20"] = logret.groupby(df["ticker"]).transform(
        lambda s: s.rolling(20, min_periods=15).std().shift(1)
    )
    df["vol_med20"] = g["volume"].transform(
        lambda s: s.rolling(20, min_periods=15).median().shift(1)
    )
    dollar_volume = df["close"] * df["volume"]
    df["dollar_vol_med20"] = dollar_volume.groupby(df["ticker"]).transform(
        lambda s: s.rolling(20, min_periods=15).median().shift(1)
    )
    df["sma_trend"] = g["close"].transform(
        lambda s: s.rolling(config.TREND_SMA, min_periods=config.TREND_SMA // 2).mean()
    )

    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["prev_close"]).abs()
    low_close = (df["low"] - df["prev_close"]).abs()
    df["true_range"] = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)

    df["vol_ratio"] = df["volume"] / df["vol_med20"]
    df["ret_z"] = df["ret"] / df["sigma20"]

    # An impulse day: unusual volume AND an unusually large up day for this name.
    df["is_impulse"] = (
        (df["vol_ratio"] >= config.IMPULSE_VOLUME_MULTIPLE)
        & (df["ret_z"] >= config.IMPULSE_RETURN_Z)
        & (df["ret"] >= config.IMPULSE_RETURN_MIN)
    ).fillna(False)

    return df


def recompute_impulse(df: pd.DataFrame) -> pd.DataFrame:
    """Re-derive the impulse flag after a threshold change, without rebuilding indicators."""
    df = df.copy()
    df["is_impulse"] = (
        (df["vol_ratio"] >= config.IMPULSE_VOLUME_MULTIPLE)
        & (df["ret_z"] >= config.IMPULSE_RETURN_Z)
        & (df["ret"] >= config.IMPULSE_RETURN_MIN)
    ).fillna(False)
    return df


def add_benchmark(df: pd.DataFrame, bench: pd.DataFrame) -> pd.DataFrame:
    """Attach the benchmark close so relative strength can be computed by date."""
    b = bench[["date", "close"]].rename(columns={"close": "bench_close"})
    return df.merge(b, on="date", how="left")


# ---------------------------------------------------------------------------
# Candidate construction
# ---------------------------------------------------------------------------

def _scale(x: pd.Series, weak: float, strong: float) -> pd.Series:
    """Map a feature onto [-1, +1], linearly between the weak and strong anchors."""
    out = 2 * (x - weak) / (strong - weak) - 1
    return out.clip(-1, 1)


def candidates_for_k(df: pd.DataFrame, k: int) -> pd.DataFrame:
    """Rows where an impulse happened k sessions ago and the k days since consolidated."""
    d = df.sort_values(["ticker", "date"]).copy()
    g = d.groupby("ticker", sort=False)

    # The impulse day, k sessions back.
    d["impulse_date"] = g["date"].shift(k)
    d["impulse_ret"] = g["ret"].shift(k)
    d["impulse_vol_ratio"] = g["vol_ratio"].shift(k)
    d["impulse_ret_z"] = g["ret_z"].shift(k)
    d["impulse_volume"] = g["volume"].shift(k)
    d["impulse_tr"] = g["true_range"].shift(k)
    d["impulse_high"] = g["high"].shift(k)
    d["impulse_close"] = g["close"].shift(k)
    d["pre_impulse_close"] = g["close"].shift(k + 1)
    d["impulse_flag"] = g["is_impulse"].shift(k).fillna(False)

    # The k consolidation days, ending on this row.
    d["cons_high"] = g["high"].transform(lambda s: s.rolling(k).max())
    d["cons_low"] = g["low"].transform(lambda s: s.rolling(k).min())
    d["cons_min_close"] = g["close"].transform(lambda s: s.rolling(k).min())
    d["cons_med_volume"] = g["volume"].transform(lambda s: s.rolling(k).median())
    d["cons_mean_tr"] = g["true_range"].transform(lambda s: s.rolling(k).mean())
    d["second_impulse"] = g["is_impulse"].transform(
        lambda s: s.astype(float).rolling(k).max()
    ) > 0

    # Cumulative move over the consolidation window, for the stock and the benchmark.
    d["close_k_ago"] = g["close"].shift(k)
    d["bench_k_ago"] = g["bench_close"].shift(k)

    # Consolidation quality.
    impulse_gain = d["impulse_close"] - d["pre_impulse_close"]
    d["gain_retained"] = (d["cons_min_close"] - d["pre_impulse_close"]) / impulse_gain
    d["range_contraction"] = d["cons_mean_tr"] / d["impulse_tr"]
    d["volume_fade"] = d["cons_med_volume"] / d["impulse_volume"]

    d["consolidation_days"] = k

    qualifies = (
        d["impulse_flag"]
        & (d["dollar_vol_med20"] >= config.MIN_DOLLAR_VOLUME)
        & (d["gain_retained"] >= config.MIN_GAIN_RETAINED)
        & (d["range_contraction"] <= config.MAX_RANGE_CONTRACTION)
        & (d["volume_fade"] <= config.MAX_VOLUME_RATIO)
        & (~d["second_impulse"])            # a second explosion is a new event, not a pause
        & (d["close"] <= d["impulse_high"])  # has not already resumed above the event-day high
    )
    return d[qualifies.fillna(False)].copy()


def add_lean(d: pd.DataFrame) -> pd.DataFrame:
    """Five equally weighted features, each in [-1, +1], averaged into one score."""
    rng = (d["cons_high"] - d["cons_low"]).replace(0, np.nan)

    d["f_close_position"] = (2 * (d["close"] - d["cons_low"]) / rng - 1).clip(-1, 1)
    d["f_volume_dryup"] = _scale(1 - d["volume_fade"], config.DRYUP_WEAK, config.DRYUP_STRONG)
    d["f_gain_retained"] = _scale(d["gain_retained"], config.RETAINED_WEAK, config.RETAINED_STRONG)

    stock_cum = d["close"] / d["close_k_ago"] - 1
    bench_cum = d["bench_close"] / d["bench_k_ago"] - 1
    d["relative_strength"] = stock_cum - bench_cum
    d["f_relative"] = _scale(d["relative_strength"], config.RELATIVE_WEAK, config.RELATIVE_STRONG)

    d["f_trend"] = np.where(d["close"] >= d["sma_trend"], 1.0, -1.0)

    features = ["f_close_position", "f_volume_dryup", "f_gain_retained", "f_relative", "f_trend"]
    d["lean_score"] = d[features].mean(axis=1)
    d["lean"] = np.select(
        [d["lean_score"] >= config.LEAN_GO_THRESHOLD,
         d["lean_score"] <= config.LEAN_STALL_THRESHOLD],
        ["leaning go", "leaning stall"],
        default="unclear",
    )
    d["reason"] = [_reason(row) for _, row in d.iterrows()]
    return d


def _reason(row: pd.Series) -> str:
    """One line a human can read, naming the two features doing the most work."""
    parts = {
        "closed near the top of the range": row["f_close_position"],
        "volume dried up": row["f_volume_dryup"],
        "held the move": row["f_gain_retained"],
        "outperformed SPY while resting": row["f_relative"],
        "above its 50-day": row["f_trend"],
    }
    negatives = {
        "closed near the bottom of the range": -row["f_close_position"],
        "volume never faded": -row["f_volume_dryup"],
        "gave back much of the move": -row["f_gain_retained"],
        "lagged SPY while resting": -row["f_relative"],
        "below its 50-day": -row["f_trend"],
    }
    pool = parts if row["lean_score"] >= 0 else negatives
    top = sorted(pool.items(), key=lambda kv: -kv[1])[:2]
    lead = "Leaning go" if row["lean_score"] >= config.LEAN_GO_THRESHOLD else (
        "Leaning stall" if row["lean_score"] <= config.LEAN_STALL_THRESHOLD else "Unclear")
    return (f"{lead}: {top[0][0]} and {top[1][0]} after a "
            f"{row['impulse_ret'] * 100:.0f}% day on {row['impulse_vol_ratio']:.1f}x volume.")


def build_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """All candidates across the allowed consolidation lengths, freshest impulse wins."""
    frames = []
    for k in config.CONSOLIDATION_DAYS:
        c = candidates_for_k(df, k)
        if not c.empty:
            frames.append(add_lean(c))
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["date", "ticker", "consolidation_days"])
    out = out.drop_duplicates(subset=["date", "ticker"], keep="first")
    return out.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Outcomes. Forward-looking on purpose, used only for evidence.
# ---------------------------------------------------------------------------

def add_outcomes(candidates: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Attach the next session's result to each candidate.

    'Goes again' = next close above the highest high of the consolidation days.
    The next session is normally Friday; in a holiday week it is the next trading day,
    which is noted in the evidence write-up.
    """
    p = prices.sort_values(["ticker", "date"]).copy()
    g = p.groupby("ticker", sort=False)
    p["next_date"] = g["date"].shift(-1)
    p["next_close"] = g["close"].shift(-1)
    p["next_high"] = g["high"].shift(-1)
    nxt = p[["date", "ticker", "next_date", "next_close", "next_high", "bench_close"]].rename(
        columns={"bench_close": "bench_close_t"}
    )

    b = prices[["date", "bench_close"]].drop_duplicates().sort_values("date")
    b["bench_next_close"] = b["bench_close"].shift(-1)

    out = candidates.merge(nxt, on=["date", "ticker"], how="left", suffixes=("", "_p"))
    out = out.merge(b[["date", "bench_next_close"]], on="date", how="left")

    out["outcome_go"] = out["next_close"] > out["cons_high"]
    out["next_return"] = out["next_close"] / out["close"] - 1
    out["bench_next_return"] = out["bench_next_close"] / out["bench_close"] - 1
    out["excess_next_return"] = out["next_return"] - out["bench_next_return"]
    return out.dropna(subset=["next_close"])
