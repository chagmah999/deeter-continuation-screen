# Note: "alert me if I'm doing well quickly on many positions"

You don't want a P&L readout. You want to know when the book is suddenly working harder
than usual in your favor, because that's when you'd press or take something off, and it's
easy to miss while you're busy.

**Doing well.** Unrealized P&L from your entry, measured in the position's own daily
move rather than dollars. One unit = a normal day for that name. A position counts at
+1.0 unit. Dollars alone let the biggest position decide; percentages alone make the
jumpiest name the whole alert.

**Quickly.** Same session, since entry. A position grinding up for two weeks isn't news.
I'd also run a two-day version and see which one you actually act on.

**Many.** The larger of five positions or 40% of open positions, all in the same
direction as your book. Five because three is a coincidence; the percentage so it still
means something on a day you only have eight on.

**The part that matters most.** Measure each position against what the market already
explains. If SPY is up 1.5% and everything long is green, that's beta, not your read.
Fire on the idiosyncratic piece. Without this filter the alert goes off on every rally
day and you'll mute it inside a week.

**How often.** My guess is a few times a month, clustered on high-dispersion days. Before
turning it on I'd replay it over six months of your blotter and count, instead of
guessing. If it comes out above roughly six a month, I'd raise the bar from 1.0 to 1.5
units rather than loosen "many". The value is in it being rare.

**Keeping it honest.** Fire once per episode: breadth has to fall back under half the
threshold before it can fire again, plus a two-hour cooldown. Nothing in the first
fifteen minutes, when marks are noisy. One line when it fires: how many positions, the
total in risk units, the three biggest contributors. And log every firing next to what
you did. If you haven't acted on one in a month, the thresholds are wrong or the alert
isn't worth having, and I'd kill it rather than leave it buzzing.

**Two things I'd want from you.** Whether "doing well" runs from entry or from yesterday's
close, and whether you want the mirror: the same logic firing when a lot of positions go
against you quickly. Same code, and probably worth more money.
