# Review of tool.py

## 1. Errors are returned as successful conversions

**What is wrong:**
The `convert` function catches every exception and returns a normal response with HTTP 200, `rate: 0.0`, and `result: 0.0`.

**Customer impact:**
An upstream failure can look like a successful conversion. An agent or user could trust the zero result instead of knowing that the exchange rate could not be retrieved.

**How I would verify it:**
Make the upstream return a 500 response or invalid JSON, then call `/tools/convert`. The service still returns HTTP 200 with a zero conversion instead of a non-2xx error.

## 2. The returned rate date can be incorrect

**What is wrong:**
`fetch_rate` returns the requested date (`on`) as `rate_date` instead of using the actual `date` field from the upstream response. This is especially problematic when the upstream falls back to `/latest` for weekends or holidays.

**Customer impact:**
The customer can be told that a conversion uses a rate from a specific date when the actual rate came from another date. This makes the result misleading and can affect decisions that depend on the rate date.

**How I would verify it:**
Return a fake upstream response where the requested date is `2026-08-30` but the response contains `"date": "2026-08-28"`. Check that the service incorrectly reports `rate_date` as `2026-08-30`.

## 3. Rates are cached without the requested date

**What is wrong:**
The cache key only contains the source and target currencies:

```python
key = f"{base}-{target}"
```

The requested date is not part of the key.

**Customer impact:**
After one date is requested, a request for a different date can reuse the previous date's rate. The customer may receive a valid-looking but incorrect historical conversion.

**How I would verify it:**
Call the endpoint twice with the same currencies but two different dates. Make the fake upstream return different rates for the two dates. The second request incorrectly reuses the first cached rate.

## 4. The rate is rounded before the conversion

**What is wrong:**
The upstream rate is rounded to two decimal places before multiplying it by the amount:

```python
rate = round(rate, 2)
result = round(amount * rate, 2)
```

**Customer impact:**
This can produce an incorrect conversion amount. The customer loses precision that was available from the upstream rate.

**How I would verify it:**
Use an upstream rate such as `56.1718` and an amount of `250`. The implementation rounds the rate to `56.17` before calculating, producing `14042.50` instead of `14042.95`.

## The one I would fix before shipping tonight

I would fix the error handling first. Returning HTTP 200 with a zero conversion when the upstream fails is the most dangerous issue because it turns a system failure into something that looks like a valid result. The caller has no reliable way to distinguish a real zero conversion from an upstream failure.

## Things that look suspicious but are fine

The in-process cache itself is reasonable for a small service. Caching a previously fetched rate can reduce unnecessary upstream requests. The problem is the cache key: it needs to include the requested date.

Using `round(..., 2)` for the final monetary result is also reasonable. The problem is rounding the exchange rate before performing the multiplication.
