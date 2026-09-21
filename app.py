import os
from datetime import date
from decimal import Decimal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


app = FastAPI(title="FX Conversion Tool")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_request",
            "message": "request parameters are invalid",
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
    )


UPSTREAM_BASE = os.getenv(
    "FX_UPSTREAM_BASE",
    "https://api.frankfurter.dev",
)

PORT = int(os.getenv("PORT", "8080"))

currency_cache = None
rate_cache = {}


async def get_currencies():
    global currency_cache

    if currency_cache is not None:
        return currency_cache

    url = f"{UPSTREAM_BASE}/v1/currencies"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail={
                "error": "upstream_timeout",
                "message": "exchange rate service timed out",
            },
        )

    if response.status_code >= 500:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_error",
                "message": "exchange rate service returned an error",
            },
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_error",
                "message": "exchange rate service returned an unexpected status",
            },
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_invalid_response",
                "message": "exchange rate service returned invalid JSON",
            },
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail={
                "error": "upstream_invalid_response",
                "message": "exchange rate service returned an unexpected response",
            },
        )

    currency_cache = data
    return currency_cache


@app.get("/tools/convert")
async def convert(
    amount: Decimal = Query(...),
    from_currency: str = Query(..., alias="from"),
    to_currency: str = Query(..., alias="to"),
    asked_date: date = Query(..., alias="date"),
):
    from_code = from_currency.upper()
    to_code = to_currency.upper()

    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_amount",
                "message": "amount must be greater than zero",
            },
        )

    decimal_places = max(0, -amount.as_tuple().exponent)

    if decimal_places >= 10:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_amount_precision",
                "message": "amount must have fewer than 10 decimal places",
            },
        )

    if asked_date > date.today():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "future_date",
                "message": "date cannot be in the future",
            },
        )

    if from_code == to_code:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "same_currency",
                "message": "from and to currencies must be different",
            },
        )

    currencies = await get_currencies()

    if from_code not in currencies:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_currency",
                "message": f"invalid currency code: {from_code}",
            },
        )

    if to_code not in currencies:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_currency",
                "message": f"invalid currency code: {to_code}",
            },
        )

    cache_key = (
        from_code,
        to_code,
        asked_date,
    )

    if cache_key in rate_cache:
        rate, rate_date = rate_cache[cache_key]
    else:
        url = f"{UPSTREAM_BASE}/v1/{asked_date}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    url,
                    params={
                        "base": from_code,
                        "symbols": to_code,
                    },
                )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "upstream_timeout",
                    "message": "exchange rate service timed out",
                },
            )

        if response.status_code >= 500:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_error",
                    "message": "exchange rate service returned an error",
                },
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "rate_not_available",
                    "message": "no exchange rate is available for the requested date",
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_error",
                    "message": "exchange rate service returned an unexpected status",
                },
            )

        try:
            data = response.json()
        except ValueError:
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_invalid_response",
                    "message": "exchange rate service returned invalid JSON",
                },
            )

        try:
            rate = Decimal(str(data["rates"][to_code]))
            rate_date = date.fromisoformat(data["date"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_invalid_response",
                    "message": "exchange rate service returned an unexpected response",
                },
            )

        rate_cache[cache_key] = (rate, rate_date)

    result = amount * rate

    return {
        "amount": amount,
        "from": from_code,
        "to": to_code,
        "rate": rate,
        "result": result,
        "rate_date": rate_date,
        "asked_date": asked_date,
        "source": "ECB via frankfurter.dev",
    }