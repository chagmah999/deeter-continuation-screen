# Thursday night continuation screen

Two PM messages, turned into something that runs.

Message 1 becomes a screen: names that had one loud up day this week, then went quiet
without giving it back, with a lean on whether Friday resumes. Message 2 is a design
question, not code, so it's answered in `notes/note_2_fast_pnl_alert.md`.

Free daily data from Yahoo, 178 liquid US names. Four hours, so the screen is small and
the evidence is modest.

## The definitions

| His words | Rule | Number | Why |
|---|---|---|---|
| "everyone is excited about" | A big up day for that name | return >= 2.5 sigma of its own 20-day vol, and >= 4% | Sigma makes the bar mean the same thing in a utility and a semi name. The 4% floor stops a dead-quiet stock qualifying on a 1.5% move that excites nobody. |
| "with volume" | Volume vs its own 20-day median | >= 3x | Catches unusual, not merely busy. |
| (tradable) | 20-day median dollar volume | >= $20mm | He has to get in and out in a day. |
| "a few consolidation days" | Days since the event | 2, 3 or 4 | One day is the day after, not a test. Past four the move is stale and Friday isn't about it anymore. |
| it held | Worst close since, as a share of the gain | >= 50% retained | Giving back more than half is a failed move, not a rest. |
| it went quiet | Mean true range vs the event day's range | <= 0.70x | Consolidation means contraction. |
| people stopped chasing | Median volume vs event day volume | <= 0.80x | Loose on purpose: the day after is still busy. |
| still a setup | Thursday close vs the event day high | at or below | If it's already closing above that, it went again without waiting for Friday. |
| "goes again" | Next close above the highest high of the quiet days | close-based | A high can be a wick. He holds overnight. |
| "stalls" | Anything else | | Lumps "sat there" with "rolled over". See below. |
| "leaning" | Five features, equal weights, scaled to [-1, +1] | go >= +0.20, stall <= -0.20 | Equal weights because nothing here is fitted. Bands set before looking at any outcome. |

The five lean features, all known at Thursday's close: where it closed in the range, how
much volume dried up, how much of the move it held, how it did against SPY while resting,
and whether it's above its 50-day.

## Where his words could mean two things

I picked one reading each time. These are the calls I'd want checked.

1. **Excited how.** Price and volume (what I used), attention, or options activity. The
   tape is the only one I can get honestly at history length.
2. **Up only.** He runs long/short, so a loud down day is arguably the mirror setup. I
   kept it to up days because "goes again Friday" reads as continuation. The mirror is a
   one-line change.
3. **A few days, or the rest of the week.** I fixed the count at 2 to 4. The calendar
   reading is probably closer to the picture in his head, but it breaks in a holiday week.
4. **Breaking out.** Intraday tag of the range high, a close above it (my choice), or just
   a green Friday. Intraday would label more names "go" and flatter the screen.
5. **Stalling.** "Didn't break out" or "failed and reversed". Very different for a
   long/short book. The evidence reports next-day return next to the go rate so both are
   visible.
6. **Holiday weeks.** The screen still runs Thursday; the outcome uses the next session.

## Running it

```bash
pip install -r requirements.txt
python -m src.screen        # tonight's list
python -m src.evidence      # the historical check, writes output/evidence.md
python control_check.py     # the unconditional "goes again" rate
python -m pytest -q         # 7 tests, one of them a look-ahead check
```

No network:

```bash
python -m src.make_sample_data
python -m src.screen --offline --date 2026-09-10
```

That panel is synthetic. It exists so the code runs anywhere, and every output it produces
is stamped as fake.

Downloads run in batches of 20 with retries, because Yahoo rate-limits large requests and
yfinance reports the failures without raising. There's a coverage check that stops the run
if fewer than 90% of tickers come back; I added it after a silent failure left me screening
50 names out of 179 and drawing a conclusion that later reversed.

Outputs land in `output/`. Prices are cached in `data/cache/`, so a rerun gives the same
list; `--refresh` re-downloads. Thresholds all live in `src/config.py`.

Deliverables: definitions above and in `config.py`; screen in `src/screen.py`; evidence in
`output/evidence.md`; the two notes in `output/note_to_pm_2026-09-24.md` and
`notes/note_2_fast_pnl_alert.md`.

## What the evidence says

76 candidates across 46 Thursdays since August 2024. Four things worth knowing before you
read the file.

**It fires about twice a month, not a few times a week.** He said these show up weekly, so
my rules are tighter than his eye. I'd rather show that than quietly loosen thresholds
until the list looked right.

**The lean does separate, weakly.** Names it likes cleared their range 14% of the time
against 4% for the rest, which is about 1.6 standard errors on this sample. Suggestive,
not settled. It doesn't separate on returns at all, so it picks names that clear a range,
not names that pay more.

**The pool underperforms the unconditional bar.** Candidates went again 11% of the time
against 17.3% for the same test applied to every name on every Thursday. Part of that is
real and part is my outcome definition: after a big move the range is wide, so the
breakout level sits much further from Thursday's close than it does for a quiet name. On
next-day returns the candidates beat the base (+0.55% vs +0.10% median). Mild
continuation, not breakouts.

**Two-day consolidations are the only ones that hold up.** They go again 20% against a
19.7% base rate, while three and four-day setups run at 4% against 16.8% and 14.8%. If I
kept one change, it would be to restrict the screen to two days.

Tonight's list also shows a flaw the numbers don't: the top-scoring name is a merger arb
situation, pinned under a cash deal price, which my features read as a perfect
consolidation. The evidence file explains it.

## What it doesn't know, and the traps

Daily bars only. No flow, no short interest, no news, no deals.

- **Survivorship.** The universe is today's liquid names.
- **Look-ahead.** Trailing stats are shifted so a day is never judged against a window
  containing itself, and the outcome lives in its own function the lean never touches. A
  test truncates the future and asserts nothing changes. The one leak I can't fix: Yahoo's
  prices carry today's adjustments, not that evening's.
- **Clustered events.** Candidates bunch into earnings season, so 76 rows across 46
  Thursdays is not 76 independent draws.
- **An unmatched control.** The 17.3% base rate runs the same test on names that aren't
  comparable. Right first comparison, wrong last one.
- **Thresholds.** Set from his description, then left alone. The grid shows nine
  combinations and that's the whole count. The 4x volume cell looks best and I didn't take
  it; it's 37 names and still below the base rate.
- **Corporate actions.** Nothing identifies deals, halts or splits.
- **Costs.** Nothing subtracts spread, and these names are wide the morning after.
- **Volume and splits.** Yahoo back-adjusts prices but not volume, so a name can register a
  false impulse for up to 20 sessions after a split.
- **One missing ticker.** X didn't download; the universe is 178 of 179.

## What I'd do next

In order: restrict to two-day consolidations, normalize the outcome bar so the go rate is
comparable across setups, and add a corporate-actions filter so deals stop scoring as
perfect consolidations. After that, split candidates by whether the event day was
accumulation or short covering, which needs intraday prints and borrow data and which I'd
bet separates the winners better than anything on this page.

---

This is an afternoon on daily bars. It's a defensible way to get a short list in front of
you Thursday night, not a claim that the pattern makes money. The honest summary is that
the setup produces mild continuation, the lean is weakly informative, and the most useful
thing I found is which parts don't work and why.

AI use: I used Claude to write most of this code and to draft the notes. The rules,
thresholds and definitions are mine, and I checked the outputs against the hand-built
cases in `tests/`, including the look-ahead and outcome logic.
