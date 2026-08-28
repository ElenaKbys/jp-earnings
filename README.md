# Post-Earnings-Announcement Drift in Japanese Equities

Measuring whether Japanese stock prices fully incorporate earnings news on the
day it arrives, or keep drifting for weeks afterwards.

**Status:** in progress.

---

## Pre-registered specification

Written before looking at any results, so that the robustness checks below
cannot be mistaken for specification search.

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

Reported as robustness, **not** selected between: market-adjusted returns
(beta forced to 1), alternative event windows, alternative liquidity thresholds.

## Day-0 convention

Most tanshin are released after the 15:30 close. If disclosure happens at or
after 15:00 on date *t*, the first tradable reaction is the next business day,
and that day is event day 0. If disclosure is before 15:00, date *t* is day 0.
Getting this off by one shifts the entire event window.

## Deviations from the original brief

The brief was written in Aug 2026 against the v1 API and needs three corrections.

**1. All endpoint paths changed in API v2.**

| Brief (v1) | Actual (v2) |
|---|---|
| `/listed/info` | `/equities/master` |
| `/prices/daily_quotes` | `/equities/bars/daily` |
| `/fins/statements` | `/fins/summary` |
| `/fins/announcement` | `/fins/earnings-date` |
| `/indices/topix` | `/indices/bars/daily/topix` |

Base URL is `https://api.jquants.com/v2`. Authentication is a single API key
in an `x-api-key` header — not the email/password → refreshToken → idToken
flow the brief describes, which was v1.

**2. TOPIX is not on the free plan.** `/indices/bars/daily/topix` requires the
Light plan. The market model therefore uses an equal-weighted index built from
the cross-section of the sample universe. This is a standard alternative, and
it has a wrinkle worth stating: because announcements cluster in the same
fortnight, the constructed index is itself partly composed of announcing firms,
so it absorbs some of the very effect being measured. This biases the estimated
drift **towards zero**, making the test conservative.

**3. SUE (surprise Option A) is not feasible on the free plan.** The seasonal
random walk needs 8 seasonal differences, so ~12 quarters of earnings history.
The free plan carries 2 years — 8 quarters. Option B (announcement-window
return) is therefore the primary and only surprise measure.

Free-plan limits that shaped the design: 2 years of history, 12-week delay,
**5 requests/minute**. The rate limit is why all fetching is done by date
rather than by security code — one request returns the whole cross-section for
a day (~490 requests) instead of one request per stock (~4,000).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # then paste your key from https://jpx-jquants.com/
python src/discover.py  # verify the key and inspect live response schemas
```

## Sources

Ball & Brown (1968); Bernard & Thomas (1989, 1990); MacKinlay (1997);
Boehmer, Musumeci & Poulsen (1991).
