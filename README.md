# Post-Earnings-Announcement Drift in Japanese Equities

Does the Japanese market actually price earnings news on day one, or do stocks keep drifting in the same direction for weeks? This repo is a data pipeline and event study built to find out.

**Status:** Work in progress.

---

## Pre-registered specification

I locked in the table below before running any numbers to avoid p-hacking or accidental specification searching once the results are in. 

| Choice | Primary specification |
|---|---|
| Universe | TSE Prime constituents, liquidity-filtered |
| Event | First disclosure of a quarterly/annual earnings summary (*tanshin*) |
| Day 0 | First tradable session after disclosure (see convention below) |
| Estimation window | `[-150, -30]` trading days |
| Event window | `[-1, +60]` trading days; drift measured over `[+2, +60]` |
| Normal return | Market model, OLS, vs an equal-weighted market index |
| Surprise measure | `CAR[-1, +1]` (announcement-window abnormal return) |
| Sorting | Quintiles, assigned **within** each announcement period |
| Headline number | `Q5 - Q1` cumulative abnormal return over `[+2, +60]` |
| Inference | Naive t-stat reported, then standard errors clustered by announcement date |

I do look at a few alternatives (market-adjusted returns, different event windows, stricter liquidity filters), but strictly as robustness checks, not cherry-picked replacements for the primary spec.

## Day-0 convention

In Japan, most *tanshin* drop after the 15:30 close, so timing is tricky. If a disclosure hits at or after 15:00 on date *t*, no one can trade it until the next session, making the *next* day event day 0. Anything before 15:00 makes date *t* day 0. Mess this up by a single day, and the entire event window is off.

## API notes

I'm using the [J-Quants API](https://api.jquants.com/v2) with a standard `x-api-key` header. The setup is simple, but the constraints of their free tier dictated a lot of the architecture:

*   **No TOPIX on the free plan.** Because of this, the market model relies on an equal-weighted index built from our sample universe. There's a catch here: Japanese earnings announcements cluster heavily in specific weeks. As a result, the benchmark index ends up containing the very stocks we're studying, which absorbs some of the anomaly. This biases the drift estimate **towards zero**. It makes the test more conservative, but it’s worth keeping in mind.
*   **SUE (Standardized Unexpected Earnings) Option A is out.** Calculating a seasonal random walk requires about 12 quarters of history, but the free plan only gives us 2 years (8 quarters). That makes announcement-window return (Option B) our only viable surprise measure.
*   **Rate limits.** The free tier has a 12-week data delay and a hard limit of **5 requests/minute**. To avoid getting throttled, the pipeline fetches data by date rather than by ticker. Pulling by date grabs the whole cross-section in one request (~490 requests total) instead of taking hours to pull ~4,000 individual stocks.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env    # then paste your key from [https://jpx-jquants.com/](https://jpx-jquants.com/)
python src/discover.py  # verify the key and inspect live response schemas