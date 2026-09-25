"""
Generate data/sample_prices.csv: a synthetic panel so the pipeline runs and the tests
pass with no network. These are not real prices and must never be read as a result.

    python -m src.make_sample_data
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample_prices.csv"

FAKE_TICKERS = [f"SYN{i:02d}" for i in range(1, 41)]
N_DAYS = 500
SEED = 7


def _one_series(rng: np.random.Generator, n: int, price0: float, daily_vol: float,
                base_volume: float, inject: bool) -> pd.DataFrame:
    ret = rng.normal(0.0003, daily_vol, n)
    vol_mult = np.exp(rng.normal(0, 0.35, n))

    if inject:
        # Plant impulse-then-consolidation patterns so the rules have something to find.
        for start in rng.choice(np.arange(60, n - 10), size=max(2, n // 90), replace=False):
            ret[start] = daily_vol * rng.uniform(3.0, 5.0)
            vol_mult[start] = rng.uniform(3.5, 7.0)
            k = rng.integers(2, 5)
            drift = rng.choice([-1.0, 1.0])  # some hold, some leak back
            for j in range(1, k + 1):
                ret[start + j] = drift * daily_vol * rng.uniform(0.05, 0.5)
                vol_mult[start + j] = rng.uniform(0.35, 0.8)

    close = price0 * np.exp(np.cumsum(ret))
    intraday = np.abs(rng.normal(0, daily_vol * 0.6, n))
    high = close * (1 + intraday)
    low = close * (1 - intraday)
    open_ = close / (1 + ret * rng.uniform(0.2, 0.8, n))
    high = np.maximum.reduce([high, close, open_])
    low = np.minimum.reduce([low, close, open_])
    volume = (base_volume * vol_mult).round()
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def main() -> None:
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=N_DAYS)
    frames = []

    for t in FAKE_TICKERS:
        df = _one_series(rng, N_DAYS, price0=rng.uniform(20, 300),
                         daily_vol=rng.uniform(0.012, 0.035),
                         base_volume=rng.uniform(1e6, 8e6), inject=True)
        df.insert(0, "ticker", t)
        df.insert(0, "date", dates)
        frames.append(df)

    spy = _one_series(rng, N_DAYS, price0=450, daily_vol=0.008, base_volume=8e7, inject=False)
    spy.insert(0, "ticker", "SPY")
    spy.insert(0, "date", dates)
    frames.append(spy)

    out = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, float_format="%.4f")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out):,} rows, {out['ticker'].nunique()} tickers")


if __name__ == "__main__":
    main()
