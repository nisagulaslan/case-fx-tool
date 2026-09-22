# Review of tool.py

## 1. `from` and `date` query parameters never actually bind

**What is wrong:**

The signature uses `from_` and `on` with no `alias`:

```python
async def convert(amount: float, from_: str = "EUR", to: str = "TRY",
                  on: date | None = None) -> dict:
```

The brief's own example URL uses `from` and `date`. FastAPI binds by argument name, so `from` and `date` are unrecognized and silently dropped. Every call falls back to `from_="EUR"` and `on=None` (today).

**Customer impact:**

Any call using the documented interface, including the brief's own example, is answered as EUR→TRY as of today, no matter what was actually asked. No error is returned. This isn't an edge case. It breaks every request that relies on the documented `from` or `date` parameters. The response also has no `asked_date` field, so even a caller who noticed the mismatch couldn't confirm what was actually used.

**How I would verify it:**

Call with `from=USD&date=2026-08-28` vs `from=EUR`. Both return `"from": "EUR"` and today's date. I ran this and confirmed it.

## 2. Errors are returned as successful conversions

**What is wrong:**

`convert` catches every exception and returns HTTP 200 with `rate: 0.0` and `result: 0.0` instead of a non-2xx error.

**Customer impact:**

An upstream failure is indistinguishable from a real zero-value conversion. The agent has no signal to tell the customer the rate couldn't be fetched. It just looks like a valid answer.

**How I would verify it:**

Make the upstream return a 500 or invalid JSON, then call `/tools/convert`. It still returns HTTP 200 with a zero result.

## 3. Date is not treated as real request state

**What is wrong:**

Two related bugs share one root cause. The service doesn't track dates correctly end to end:

* `fetch_rate` returns `str(on or date.today())` as `rate_date`. It never reads `payload["date"]` from the upstream response, so the reported date is whatever was requested, not what the rate actually belongs to.
* The cache key is `f"{base}-{target}``. It does not include the date. Once a rate is cached for one date, every later request for that currency pair reuses it regardless of what date is asked.

**Customer impact:**

The customer can be told a rate is from a date it isn't from, and can get a stale rate for a date that was never actually queried. This is the exact failure the task brief calls out directly: never present a rate as belonging to a date it doesn't belong to.

**How I would verify it:**

Mock the upstream so the requested date is `2026-08-30` but the response body says `"date": "2026-08-28"`. The service reports `rate_date` as `2026-08-30`. Separately, call the endpoint for two different dates with different mocked rates. The second call incorrectly returns the first call's cached rate.

## The one I would fix before shipping tonight

Finding #1. It's not an edge case. It silently breaks the documented interface for essentially all real traffic, with nothing to catch it in testing or logs. Fixing it also ensures the service actually respects the documented request parameters.

## Also worth noting

The rate is rounded to 2 decimals *before* multiplying by the amount (`round(rate, 2)` then `round(amount * rate, 2)`), which loses precision. For example, a real rate of `56.1718` becomes `56.17`, turning 250 units into `14042.50` instead of the correct `14042.95`. This is a real issue, but smaller in impact than the three above, so I'm not giving it full treatment here.
