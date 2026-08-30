# Post-Earnings-Announcement Drift in Japanese Equities

Does the Japanese market fully price earnings news on the day it lands, or
does the stock keep drifting in the same direction for weeks afterward? This
is a data pipeline and event study built to find out.

**Status:** in progress.

---

## Pre-registered specification

The table below was locked in before looking at any results. That's the whole
point of pre-registering it: once real numbers come back, the robustness
checks further down can't quietly turn into specification search.

| Choice | Primary specification |
|---|---|
| Universe | TSE Prime constituents, liquidity-filtered |
| Event | First disclosure of a quarterly/annual earnings summary (tanshin) |
| Day 0 | First tradable session after disclosure (see convention below) |
| Estimation window | `[-150, -30]` trading days |
| Event window | `[-1, +60]` trading days; drift measured over `[+2, +60]` |
| Normal return | Market model, OLS, vs an equal-weighted market index |
| Surprise measure | `CAR[-1, +1]` (announcement-window abnormal return) |
| Sorting | Quintiles, assigned **within** each announcement period |
| Headline number | `Q5 - Q1` cumulative abnormal return over `[+2, +60]` |
| Inference | Naive t-stat reported, then standard errors clustered by announcement date |

A few alternatives — market-adjusted returns (beta forced to 1), other event
windows, other liquidity thresholds — get reported too, but only as
robustness, never as options to pick a winner from.

## Day-0 convention

Most tanshin drop after the 15:30 close, so timing matters more than it
sounds like it should. If disclosure happens at or after 15:00 on date *t*,
nobody can trade on it until the next session, so that next day becomes event
day 0. Anything before 15:00 and date *t* itself is day 0. Get this wrong by
one day and the entire event window shifts with it.

## API notes

Base URL is `https://api.jquants.com/v2`, authenticated with a single API key
in an `x-api-key` header. Straightforward enough — the free plan is where the
real constraints live.

**TOPIX isn't on the free plan**, so the market model uses an equal-weighted
index built from the sample universe itself instead. That has a wrinkle worth
flagging: announcements cluster in the same fortnight, so the constructed
index ends up partly composed of the very firms being studied, and it absorbs
some of the effect it's supposed to be a benchmark against. That biases the
estimated drift **towards zero** — not a fatal flaw, just something that makes
the test conservative rather than invalid.

**SUE Option A is off the table too.** It needs a seasonal random walk over 8
seasonal differences, which means ~12 quarters of earnings history, and the
free plan only goes back 2 years (8 quarters). So Option B —
announcement-window return — isn't just the primary surprise measure, it's
the only one available.

The plan's other limits — 12-week data delay, **5 requests/minute** — are
what actually shaped the fetching strategy. That rate limit is why everything
is pulled by date instead of by security code: one request returns the whole
day's cross-section (~490 requests total) rather than one request per stock
(~4,000 requests, and a much longer wait).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # then paste your key from https://jpx-jquants.com/
python src/discover.py  # verify the key and inspect live response schemas
```

## Sources

Standing on the shoulders of Ball & Brown (1968), Bernard & Thomas (1989,
1990), MacKinlay (1997), and Boehmer, Musumeci & Poulsen (1991) — the drift
itself, the standard event-study machinery, and the case for clustering
standard errors by event date all come from this line of work.
