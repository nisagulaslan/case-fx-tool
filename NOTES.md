# Notes

## Decisions

* The endpoint only accepts dates up to today. Future dates return `future_date`.

* Invalid or unknown currencies return `invalid_currency`. `from` and `to` cannot be the same.

* The amount must be greater than zero and must have fewer than 10 decimal places.

* For weekends and holidays, Frankfurter may return the most recently published rate. I use the `date` field returned by the upstream as `rate_date`, while keeping the requested date as `asked_date`. This makes it explicit when the actual rate date differs from the requested date. Tested explicitly with a case where the two dates differ.

* If no rate is available for the requested date, the service returns `rate_not_available` rather than inventing or silently substituting a rate.

* Upstream timeouts return `504 upstream_timeout`. Upstream server errors or invalid responses return a non-2xx error instead of returning a made-up conversion.

* Rates are cached by source currency, target currency, and requested date. The amount is intentionally not part of the cache key because the same rate can be reused for different amounts.

* `result` is quantized to 2 decimal places (`ROUND_HALF_UP`) after multiplying the full-precision rate by the amount, rather than rounding the rate first, to avoid losing precision before the conversion.

## With another day

I would consider a bounded cache strategy for a long-running production service and add more tests around different upstream response shapes, such as malformed rates, unexpected currency sets, and partial JSON.

## AI tools

I used an AI coding assistant while implementing the service and tests. I reviewed the generated code, ran the application locally, tested the endpoint, and wrote tests with a fake upstream so that the test suite does not require network access.

## One thing the AI got wrong

The initial implementation/testing approach did not account for shared in-process cache state between tests. A previous successful conversion could remain cached and cause a later upstream-error test to return `200` instead of exercising the upstream failure path. I noticed this when the test unexpectedly returned `200`, then cleared the rate cache in the relevant tests and verified the complete suite again.
