"""
What happened on Fridays when these rules fired.

    python -m src.evidence --offline
    python -m src.evidence

Writes output/evidence.md. This is a check, not a backtest of a strategy: no costs,
no sizing, no exits. It exists to say whether the lean carries information and to be
honest about how little the sample can support.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, data, rules

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


def build_panel(offline: bool, refresh: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = data.load_prices(offline=offline, refresh=refresh)
    universe, bench = data.split_benchmark(prices)
    universe = rules.add_indicators(universe)
    universe = rules.add_benchmark(universe, bench)
    return universe, bench


def thursday_candidates(universe: pd.DataFrame) -> pd.DataFrame:
    cand = rules.build_candidates(universe)
    if cand.empty:
        return cand
    # The PM asked for a Thursday night list, so the evidence is Thursday-only.
    cand = cand[cand["date"].dt.dayofweek == 3]
    return rules.add_outcomes(cand, universe)


def summarize(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    def agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n": len(g),
            "go_rate": g["outcome_go"].mean(),
            "median_next_return": g["next_return"].median(),
            "median_excess_return": g["excess_next_return"].median(),
            "up_rate": (g["next_return"] > 0).mean(),
        })
    if by is None:
        return agg(df).to_frame().T
    return df.groupby(by, sort=False).apply(agg, include_groups=False).reset_index()


def benchmark_base_rate(universe: pd.DataFrame) -> dict:
    """What a Friday looks like without any screen at all."""
    b = universe[["date", "bench_close"]].drop_duplicates().sort_values("date")
    b["next_close"] = b["bench_close"].shift(-1)
    b["next_return"] = b["next_close"] / b["bench_close"] - 1
    thurs = b[b["date"].dt.dayofweek == 3].dropna(subset=["next_return"])

    # Every screened name on every Thursday, as the "no screen" comparison.
    u = universe.sort_values(["ticker", "date"]).copy()
    u["next_close"] = u.groupby("ticker", sort=False)["close"].shift(-1)
    u["next_return"] = u["next_close"] / u["close"] - 1
    all_thurs = u[u["date"].dt.dayofweek == 3].dropna(subset=["next_return"])
    return {
        "bench_up_rate": thurs["next_return"].gt(0).mean(),
        "bench_n": len(thurs),
        "universe_up_rate": all_thurs["next_return"].gt(0).mean(),
        "universe_median_return": all_thurs["next_return"].median(),
        "universe_n": len(all_thurs),
    }


def threshold_grid(universe: pd.DataFrame) -> pd.DataFrame:
    """Re-run the whole screen under different thresholds and report every cell.

    The point is not to find the best cell. It is to show how much the answer moves
    when the numbers move, so nobody mistakes one lucky setting for a result.
    """
    rows = []
    base = (config.IMPULSE_VOLUME_MULTIPLE, config.IMPULSE_RETURN_MIN, config.LEAN_GO_THRESHOLD)
    try:
        for vol_mult in [2.5, 3.0, 4.0]:
            for ret_min in [0.03, 0.04, 0.06]:
                config.IMPULSE_VOLUME_MULTIPLE = vol_mult
                config.IMPULSE_RETURN_MIN = ret_min
                u = rules.recompute_impulse(universe)
                cand = thursday_candidates(u)
                if cand.empty:
                    rows.append({"vol_mult": vol_mult, "ret_min": ret_min, "n": 0,
                                 "go_rate": np.nan, "go_rate_leaning_go": np.nan,
                                 "go_rate_leaning_stall": np.nan})
                    continue
                go = cand[cand["lean"] == "leaning go"]
                stall = cand[cand["lean"] == "leaning stall"]
                rows.append({
                    "vol_mult": vol_mult,
                    "ret_min": ret_min,
                    "n": len(cand),
                    "go_rate": cand["outcome_go"].mean(),
                    "go_rate_leaning_go": go["outcome_go"].mean() if len(go) else np.nan,
                    "go_rate_leaning_stall": stall["outcome_go"].mean() if len(stall) else np.nan,
                })
    finally:
        (config.IMPULSE_VOLUME_MULTIPLE, config.IMPULSE_RETURN_MIN,
         config.LEAN_GO_THRESHOLD) = base
    return pd.DataFrame(rows)


def fmt(df: pd.DataFrame) -> str:
    d = df.copy()
    for col in d.columns:
        if d[col].dtype.kind == "f":
            if "rate" in col:
                d[col] = d[col].map(lambda v: "" if pd.isna(v) else f"{v:.0%}")
            elif "return" in col:
                d[col] = d[col].map(lambda v: "" if pd.isna(v) else f"{v:+.2%}")
            else:
                d[col] = d[col].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    return d.to_markdown(index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Historical check of the screen")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    universe, _ = build_panel(args.offline, args.refresh)
    cand = thursday_candidates(universe)
    base = benchmark_base_rate(universe)

    if cand.empty:
        print("No candidates in the sample.")
        return

    overall = summarize(cand)
    by_lean = summarize(cand, "lean")
    by_k = summarize(cand, "consolidation_days")
    grid = threshold_grid(universe)

    span = f"{cand['date'].min().date()} to {cand['date'].max().date()}"
    weeks = cand["date"].nunique()

    md = f"""# Evidence

Source: {data.data_source_label(args.offline)}
Sample: {len(cand)} candidates across {weeks} Thursdays, {span}.
Outcome: "goes again" = the next session closes above the highest high of the
consolidation days. The next session is normally Friday; in a holiday week it is the
next trading day.

## Overall

{fmt(overall)}

## By lean

{fmt(by_lean)}

## By number of consolidation days

{fmt(by_k)}

## Comparison: no screen at all

- Any screened name, any Thursday, next-session up rate: {base['universe_up_rate']:.0%} (n={base['universe_n']:,})
- Median next-session return, same population: {base['universe_median_return']:+.2%}
- {config.BENCHMARK} next-session up rate: {base['bench_up_rate']:.0%} (n={base['bench_n']})

A go rate only means something next to these. If the lean buckets do not separate, the
lean is decoration.

## Threshold grid

Every cell, not the best one.

{fmt(grid)}

## Traps in this check, named

1. **Survivorship.** The universe is today's liquid names, so anything delisted or
   collapsed is missing. The check is biased toward the survivors of the period.
2. **Look-ahead.** Features use only rows dated on or before the screen date, and
   trailing statistics are shifted so a day is never judged against a window containing
   itself. The outcome is computed in a separate function and never feeds the lean.
   One residual risk: Yahoo's adjusted prices are today's adjustments, not what was on
   the tape that evening.
3. **Thresholds fitted to the answer.** The numbers in config.py were chosen from how
   the PM described the setup, then left alone. The grid above shows how much they matter.
   I ran 9 threshold combinations, and that is the whole count.
4. **Overlapping and clustered events.** Candidates cluster into earnings season and
   into a handful of strong weeks, so the Fridays are not independent draws. The
   effective sample is closer to the number of distinct Thursdays ({weeks}) than to the
   number of rows.
5. **Sample size.** With this many candidates, a difference of a few percentage points
   between lean buckets is inside the noise. Treat direction, not magnitude.
6. **No costs.** Nothing here subtracts spread or impact, and these names are wide the
   morning after an event.

## What free daily data cannot test, and what I would use instead

- **Was the excitement real flow or a squeeze?** Daily bars cannot separate them.
  With intraday prints and short interest or borrow data, I would split candidates by
  whether the impulse day was accumulation or covering, which I expect matters more
  than any of the price features here.
- **Was the move fundamental?** A point-in-time earnings and revision feed would let me
  separate guide-ups from momentum, which the screen currently treats identically.
- **Did it break out cleanly?** Minute bars would let the outcome distinguish a close
  above the range from a wick and fade, which is the difference between a trade and a trap.
- **Was the setup crowded?** Options open interest and positioning data would say whether
  everyone else is looking at the same list.
"""
    OUT.mkdir(exist_ok=True)
    path = OUT / "evidence.md"
    path.write_text(md)
    print(md)
    print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
