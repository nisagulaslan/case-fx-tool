# FX Conversion Tool

A small FastAPI service that converts currencies using exchange rates from the public Frankfurter API.

## Run

Python 3.11+ is recommended.

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Start the service:

```bash
./run.sh
```

The default port is `8080`. It can be changed with:

```bash
PORT=9000 ./run.sh
```

The upstream URL can be changed with `FX_UPSTREAM_BASE`. It defaults to `https://api.frankfurter.dev`.

## Test

Tests do not use the network. The upstream HTTP client is replaced with fake responses.

```bash
./test.sh
```

On Windows without Bash/WSL, run the test command directly:

```powershell
pytest -q
```

## Endpoint

```text
GET /tools/convert?amount=250&from=EUR&to=TRY&date=2026-08-28
```

Example successful response:

```json
{
  "amount": 250,
  "from": "EUR",
  "to": "TRY",
  "rate": 56.1718,
  "result": 14042.95,
  "rate_date": "2026-08-28",
  "asked_date": "2026-08-28",
  "source": "ECB via frankfurter.dev"
}
```

result is rounded to 2 decimal places using ROUND_HALF_UP. The exchange rate itself is not rounded before the calculation.

`asked_date` is the date requested by the caller. `rate_date` is the actual date returned by Frankfurter for the rate used. They may differ for weekends or holidays.

The service never invents a rate. If the upstream returns a rate for an earlier published date, that actual date is exposed as `rate_date`.

Rates are cached by `from`, `to`, and requested date, so repeating the same conversion question does not re-request the rate from the upstream.

## Error codes

| Error                       | Status | Behavior                                            |
| --------------------------- | -----: | --------------------------------------------------- |
| `invalid_request`           |    400 | Required or otherwise invalid request parameters    |
| `invalid_amount`            |    400 | Amount is zero or negative                          |
| `invalid_amount_precision`  |    400 | Amount has 10 or more decimal places                |
| `future_date`               |    400 | Requested date is in the future                     |
| `invalid_currency`          |    400 | Currency code is not supported                      |
| `same_currency`             |    400 | `from` and `to` are the same                        |
| `rate_not_available`        |    400 | No rate is available for the requested date         |
| `upstream_timeout`          |    504 | Frankfurter does not respond within the timeout     |
| `upstream_error`            |    502 | Frankfurter returns an unexpected/error HTTP status |
| `upstream_invalid_response` |    502 | Frankfurter returns invalid or unexpected JSON      |

Dates before the available rate series are treated as `rate_not_available`.

Note: if `from` and `to` are identical but also not real currency codes,
the response is `same_currency`, not `invalid_currency` — the equality
check runs before the currency lookup.

All failures return a non-2xx status and:

```json
{
  "error": "short_machine_code",
  "message": "a human-readable explanation"
}
```
