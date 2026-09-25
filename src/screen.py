"""
The Thursday night screen.

    python -m src.screen                  # latest close, live Yahoo data
    python -m src.screen --offline        # synthetic sample data, no network
    python -m src.screen --date 2026-09-17

Writes output/screen_<date>.csv and output/note_to_pm_<date>.md.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import config, data, rules

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"

DISPLAY = [
    "ticker", "impulse_date", "impulse_ret", "impulse_vol_ratio", "consolidation_days",
    "gain_retained", "range_contraction", "volume_fade", "relative_strength",
    "close", "cons_low", "cons_high", "lean_score", "lean", "reason",
]


def run(offline: bool = False, refresh: bool = False, as_of: str | None = None) -> pd.DataFrame:
    prices = data.load_prices(offline=offline, refresh=refresh)
    universe, bench = data.split_benchmark(prices)
    universe = rules.add_indicators(universe)
    universe = rules.add_benchmark(universe, bench)

    candidates = rules.build_candidates(universe)
    if candidates.empty:
        return candidates

    screen_date = pd.Timestamp(as_of) if as_of else universe["date"].max()
    todays = candidates[candidates["date"] == screen_date].copy()
    todays = todays.sort_values("lean_score", ascending=False)
    return todays.assign(screen_date=screen_date)


def format_table(todays: pd.DataFrame) -> pd.DataFrame:
    out = todays[DISPLAY].copy()
    out["impulse_date"] = pd.to_datetime(out["impulse_date"]).dt.date
    for col, fmt in [("impulse_ret", "{:.1%}"), ("gain_retained", "{:.0%}"),
                     ("range_contraction", "{:.2f}"), ("volume_fade", "{:.2f}"),
                     ("relative_strength", "{:+.1%}"), ("lean_score", "{:+.2f}"),
                     ("impulse_vol_ratio", "{:.1f}x")]:
        out[col] = out[col].map(lambda v, f=fmt: f.format(v) if pd.notna(v) else "")
    for col in ["close", "cons_low", "cons_high"]:
        out[col] = out[col].map(lambda v: f"{v:.2f}")
    return out


def write_note(todays: pd.DataFrame, screen_date, offline: bool) -> Path:
    lines = []
    if todays.empty:
        body = "No names cleared the screen tonight. Nothing to look at Friday morning."
    else:
        body = "\n".join(
            f"- {r.ticker}: {r.lean} ({r.lean_score:+.2f}). {r.reason}"
            for r in todays.itertuples()
        )
    counts = todays["lean"].value_counts().to_dict() if not todays.empty else {}
    note = f"""# Note to the PM, {pd.Timestamp(screen_date).date()}

Source: {data.data_source_label(offline)}

**What this is.** Names that had one high-volume up day in the last week, then went quiet
without giving the move back. {len(todays)} cleared tonight
({counts.get('leaning go', 0)} leaning go, {counts.get('unclear', 0)} unclear,
{counts.get('leaning stall', 0)} leaning stall).

**Tonight's list.**
{body}

**What it does not know.** It reads daily bars only: no options flow, no short interest,
no news, no idea whether the excitement was an upgrade, a guide-up, or a squeeze.
It cannot tell a clean breakout from a wick, because the outcome is measured on the close.

**What I would test next.** Whether the move that started the week was fundamental or
positioning-driven, which is the split I expect actually separates the ones that go again.
"""
    OUT.mkdir(exist_ok=True)
    path = OUT / f"note_to_pm_{pd.Timestamp(screen_date).date()}.md"
    path.write_text(note)
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description="Thursday night continuation screen")
    ap.add_argument("--offline", action="store_true", help="use the synthetic sample panel")
    ap.add_argument("--refresh", action="store_true", help="ignore the price cache")
    ap.add_argument("--date", default=None, help="screen as of this date (default: latest close)")
    args = ap.parse_args()

    todays = run(offline=args.offline, refresh=args.refresh, as_of=args.date)
    if todays.empty:
        print("No candidates on the screen date.")
        return

    screen_date = todays["screen_date"].iloc[0]
    print(f"\nScreen date: {pd.Timestamp(screen_date).date()}")
    print(f"Source: {data.data_source_label(args.offline)}")
    print(f"Candidates: {len(todays)}\n")
    table = format_table(todays)
    print(table.drop(columns=["reason"]).to_string(index=False))
    print()
    for r in todays.itertuples():
        print(f"  {r.ticker}: {r.reason}")

    OUT.mkdir(exist_ok=True)
    csv_path = OUT / f"screen_{pd.Timestamp(screen_date).date()}.csv"
    todays[DISPLAY].to_csv(csv_path, index=False)
    note_path = write_note(todays, screen_date, args.offline)
    print(f"\nWrote {csv_path.relative_to(ROOT)} and {note_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
