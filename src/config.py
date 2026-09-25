# ---------------------------------------------------------------------------
# Universe and liquidity
# ---------------------------------------------------------------------------

# Minimum 20-day median dollar volume to be screened at all.
# $20mm/day is enough that a short-horizon book can get in and out in a day without the spread being the whole trade.
MIN_DOLLAR_VOLUME = 20_000_000

# ---------------------------------------------------------------------------
# "everyone is excited about ... with volume"  ->  the impulse day
# ---------------------------------------------------------------------------

# Volume on the impulse day, as a multiple of its own trailing 20-day median volume.
# 3x is roughly the 99th percentile of daily volume ratios for a liquid name, so it picks out days that are unusual for that stock rather than days that are merely busy.
IMPULSE_VOLUME_MULTIPLE = 3.0

# Impulse day return, in standard deviations of its own trailing 20-day daily vol.
# 2.5 sigma keeps the bar comparable across a utility and a high-beta small cap.
IMPULSE_RETURN_Z = 2.5

# Absolute floor on the impulse day return.
# Without it, a very quiet name qualifies on a 1.5% day, which no one is excited about.
IMPULSE_RETURN_MIN = 0.04

# ---------------------------------------------------------------------------
# "a few consolidation days"
# ---------------------------------------------------------------------------

# "A few" = 2 to 4 sessions between the impulse day and the screen date.
CONSOLIDATION_DAYS = (2, 3, 4)

# Worst close during consolidation must retain at least this share of the impulse gain, measured from the close before the impulse day.
# Giving back more than half the move is a failed move, not a consolidation.
MIN_GAIN_RETAINED = 0.50

# Mean true range over the consolidation days, as a multiple of the impulse day's range.
# Consolidation means quieter. 0.7 is a real contraction without demanding perfection.
MAX_RANGE_CONTRACTION = 0.70

# Median consolidation volume as a multiple of impulse day volume.
# Participation should fade after the event; 0.8 is deliberately loose because the day after a big move is still busy.
MAX_VOLUME_RATIO = 0.80

# ---------------------------------------------------------------------------
# "leaning"  ->  five features, equally weighted, each scaled to [-1, +1]
# ---------------------------------------------------------------------------

# Close position in the consolidation range: 1.0 = closed at the high of the range.
# Closing near the highs of a tight range is the classic coiled-under-resistance look.

# Volume dry-up (1 - median consolidation volume / impulse volume) that scores +1 / -1.
DRYUP_STRONG = 0.50   # participation halved: sellers are done
DRYUP_WEAK = 0.00     # no fade at all: supply is still coming

# Share of the impulse gain retained that scores +1 / -1.
RETAINED_STRONG = 0.85
RETAINED_WEAK = 0.50

# Stock return minus SPY return over the consolidation window that scores +1 / -1.
RELATIVE_STRONG = 0.01
RELATIVE_WEAK = -0.01

# Trend filter: close above/below this simple moving average scores +1 / -1.
TREND_SMA = 50

# Score bands for the printed lean. Chosen before looking at any outcome, to split
# roughly into thirds; evidence.py reports how the results change at 0.1 and 0.3.
LEAN_GO_THRESHOLD = 0.20
LEAN_STALL_THRESHOLD = -0.20

# ---------------------------------------------------------------------------
# "goes again" vs "stalls"  ->  the Friday outcome, used only in evidence.py
# ---------------------------------------------------------------------------

# Close-based: the next session closes above the highest high of the consolidation days.
# Using the close, not an intraday tag of the high, because free daily data cannot tell a clean break from a wick, and because the PM holds overnight.
# Ambiguity flagged in the README: an intraday definition would label more names "go".

# Benchmark used for relative strength and for the market-move caveat.
BENCHMARK = "SPY"

# History pulled for the screen and the evidence run.
LOOKBACK_DAYS = 800
