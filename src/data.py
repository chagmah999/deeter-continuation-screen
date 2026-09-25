"""
Price data. Free, public, and cached so a run is reproducible.

Live source: Yahoo Finance via yfinance (daily OHLCV, split/dividend adjusted prices).
Offline source: data/sample_prices.csv, a synthetic panel used by the tests and by
anyone who wants to run the pipeline without a network call. It is fake data and is
labelled as such everywhere it is used.

Downloads run in small batches with retries. Yahoo rate-limits large requests and
yfinance reports the failures without raising, so a naive one-shot download can return a
quarter of the universe and look fine. Anything short of 90% coverage stops the run.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd

from . import config

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SAMPLE_PATH = DATA_DIR / "sample_prices.csv"
UNIVERSE_PATH = DATA_DIR / "universe.csv"

COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume"]
FIELDS = ["Open", "High", "Low", "Close", "Volume"]

BATCH_SIZE = 20          # Yahoo starts refusing well before 176 at once
RETRIES = 3
PAUSE_BETWEEN_BATCHES = 2.0
MIN_COVERAGE = 0.90      # fail the run rather than screen a quarter of the universe


def load_universe() -> list[str]:
    """Tickers to screen, plus the benchmark."""
    tickers = pd.read_csv(UNIVERSE_PATH)["ticker"].dropna().astype(str).str.strip().tolist()
    if config.BENCHMARK not in tickers:
        tickers.append(config.BENCHMARK)
    return tickers


def _cache_path(tag: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"prices_{tag}.csv"


def _block_to_long(raw: pd.DataFrame, chunk: list[str]) -> pd.DataFrame:
    """Turn one yfinance block into long rows: date, ticker, open..volume."""
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=COLUMNS)

    if isinstance(raw.columns, pd.MultiIndex):
        frames = []
        for field in FIELDS:
            if field not in raw.columns.get_level_values(0):
                return pd.DataFrame(columns=COLUMNS)
            block = raw[field].stack(future_stack=True)
            block.name = field.lower()
            frames.append(block)
        df = pd.concat(frames, axis=1).reset_index()
        df.columns = ["date", "ticker"] + [f.lower() for f in FIELDS]
    else:
        # A single-ticker chunk comes back with flat columns.
        df = raw[FIELDS].copy()
        df.columns = [f.lower() for f in FIELDS]
        df = df.reset_index()
        df.columns = ["date"] + [f.lower() for f in FIELDS]
        df["ticker"] = chunk[0]

    return df[COLUMNS]


def _download(tickers: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Batched, retried download. Prints what failed instead of hiding it."""
    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("yfinance is required for live data: pip install -r requirements.txt") from exc

    # yfinance keeps a sqlite timezone cache; the default location is not always writable,
    # and when it fails every ticker comes back as "possibly delisted; no timezone found".
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(CACHE_DIR / "yf_tz"))
    except Exception:
        pass

    pieces, missing = [], []
    for i in range(0, len(tickers), BATCH_SIZE):
        chunk = tickers[i:i + BATCH_SIZE]
        block = pd.DataFrame(columns=COLUMNS)
        for attempt in range(RETRIES):
            try:
                raw = yf.download(
                    chunk,
                    start=start.date().isoformat(),
                    end=(end + pd.Timedelta(days=1)).date().isoformat(),
                    auto_adjust=True,        # prices back-adjusted for splits and dividends
                    group_by="column",
                    progress=False,
                    threads=False,           # serial requests get throttled far less
                )
                block = _block_to_long(raw, chunk)
            except Exception as exc:
                print(f"  batch {i // BATCH_SIZE + 1} attempt {attempt + 1} failed: {exc}")
                block = pd.DataFrame(columns=COLUMNS)
            got = set(block["ticker"].unique()) if len(block) else set()
            if len(got) >= len(chunk):
                break
            if attempt < RETRIES - 1:
                time.sleep(5 * (attempt + 1))

        got = set(block["ticker"].unique()) if len(block) else set()
        missing += [t for t in chunk if t not in got]
        if len(block):
            pieces.append(block)
        print(f"  batch {i // BATCH_SIZE + 1}: {len(got)}/{len(chunk)} tickers")
        time.sleep(PAUSE_BETWEEN_BATCHES)

    if missing:
        print(f"WARNING: {len(missing)} tickers returned nothing: {sorted(missing)}")

    if not pieces:
        raise SystemExit("No data returned by yfinance. Check the network and retry.")
    return pd.concat(pieces, ignore_index=True)


def load_prices(offline: bool = False, refresh: bool = False,
                lookback_days: int = config.LOOKBACK_DAYS) -> pd.DataFrame:
    """Return a long panel: date, ticker, open, high, low, close, volume."""
    if offline:
        df = pd.read_csv(SAMPLE_PATH, parse_dates=["date"])
        return df[COLUMNS].sort_values(["ticker", "date"]).reset_index(drop=True)

    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=lookback_days)
    cache = _cache_path(f"{start.date()}_{end.date()}")
    if cache.exists() and not refresh:
        df = pd.read_csv(cache, parse_dates=["date"])
        return _finalize(df, expected=len(load_universe()), from_cache=True)

    tickers = load_universe()
    print(f"Downloading {len(tickers)} tickers in batches of {BATCH_SIZE}...")
    df = _download(tickers, start, end)
    df = _finalize(df, expected=len(tickers), from_cache=False)
    df.to_csv(cache, index=False)
    return df


def _finalize(df: pd.DataFrame, expected: int, from_cache: bool) -> pd.DataFrame:
    """Clean the panel and refuse to return a badly incomplete one."""
    df = df.dropna(subset=["close", "volume"])
    df = df[df["volume"] > 0]
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    df = df[COLUMNS].sort_values(["ticker", "date"]).reset_index(drop=True)

    got = df["ticker"].nunique()
    if got < MIN_COVERAGE * expected:
        where = "The cached panel" if from_cache else "This download"
        raise SystemExit(
            f"{where} has only {got} of {expected} tickers. Yahoo was probably rate "
            f"limiting. Delete data/cache and rerun with --refresh; if it keeps failing, "
            f"trim data/universe.csv to the names that download reliably and say so in "
            f"the README."
        )
    if got < expected:
        print(f"Note: {got} of {expected} tickers present.")
    return df


def split_benchmark(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate the benchmark series from the screened universe."""
    bench = df[df["ticker"] == config.BENCHMARK].copy()
    universe = df[df["ticker"] != config.BENCHMARK].copy()
    if bench.empty:
        raise SystemExit(f"Benchmark {config.BENCHMARK} missing from the price panel.")
    return universe, bench


def data_source_label(offline: bool) -> str:
    return "SYNTHETIC SAMPLE DATA (not real prices)" if offline else "Yahoo Finance daily OHLCV via yfinance"


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes"}
