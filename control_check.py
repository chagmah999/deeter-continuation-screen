"""One-off: what does the "goes again" test do without any screen at all?

The screen's go rate has no meaning on its own. A close above the trailing k-day high is
a demanding bar for any stock on any day, so this computes the unconditional version of
the same test and weights it to match the candidates' mix of window lengths.
"""

from src import data

u, b = data.split_benchmark(data.load_prices())
print(f"Panel: {u['ticker'].nunique()} tickers, {len(u):,} rows, through {u['date'].max().date()}")

u = u.sort_values(["ticker", "date"])
g = u.groupby("ticker", sort=False)
u["next_close"] = g["close"].shift(-1)

# Candidate mix from the evidence run: update these if the candidate counts change.
mix = {2: 30, 3: 23, 4: 23}
rates, total_n = {}, 0

for k in (2, 3, 4):
    high_k = g["high"].transform(lambda s: s.rolling(k).max())
    ok = (u["date"].dt.dayofweek == 3) & u["next_close"].notna() & high_k.notna()
    rates[k] = (u["next_close"] > high_k)[ok].mean()
    total_n += int(ok.sum())
    print(f"k={k}: n={ok.sum():,}  base go rate={rates[k]:.1%}")

weighted = sum(rates[k] * w for k, w in mix.items()) / sum(mix.values())
print(f"\nWeighted to the candidate mix {tuple(mix.values())}: {weighted:.1%}  (n={total_n:,})")
