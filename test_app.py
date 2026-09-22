from fastapi.testclient import TestClient

import app


client = TestClient(app.app)


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_missing_amount():
    response = client.get(
        "/tools/convert",
        params={
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_request"


def test_same_currency():
    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "EUR",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "same_currency"


def test_invalid_currency(monkeypatch):
    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "ABC",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_currency"


def test_future_date():
    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "2099-01-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "future_date"


def test_invalid_amount():
    response = client.get(
        "/tools/convert",
        params={
            "amount": "0",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_amount"


def test_conversion_without_network(monkeypatch):
    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse(
                200,
                {
                    "amount": 1.0,
                    "base": "EUR",
                    "date": "2026-08-28",
                    "rates": {
                        "TRY": 56.1718
                    },
                },
            )

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["rate"] == 56.1718
    assert data["result"] == 14042.95
    assert data["rate_date"] == "2026-08-28"
    assert data["asked_date"] == "2026-08-28"


def test_upstream_error(monkeypatch):
    app.rate_cache.clear()

    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse(500, {})

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_error"


def test_upstream_timeout(monkeypatch):
    app.rate_cache.clear()

    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            raise app.httpx.TimeoutException("timeout")

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 504
    assert response.json()["error"] == "upstream_timeout"


def test_upstream_invalid_json(monkeypatch):
    app.rate_cache.clear()

    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    class FakeResponse:
        status_code = 200

        def json(self):
            raise ValueError("invalid json")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse()

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 502
    assert response.json()["error"] == "upstream_invalid_response"


def test_rate_not_available(monkeypatch):
    app.rate_cache.clear()

    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse(404, {})

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "1990-01-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "rate_not_available"


def test_invalid_amount_precision():
    response = client.get(
        "/tools/convert",
        params={
            "amount": "250.1234567890",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_amount_precision"


def test_rate_is_cached(monkeypatch):
    app.rate_cache.clear()

    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    call_count = 0

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            nonlocal call_count
            call_count += 1

            return FakeResponse(
                200,
                {
                    "amount": 1.0,
                    "base": "EUR",
                    "date": "2026-08-28",
                    "rates": {
                        "TRY": 56.1718
                    },
                },
            )

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    first_response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    second_response = client.get(
        "/tools/convert",
        params={
            "amount": "500",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["result"] == 14042.95
    assert second_response.json()["result"] == 28085.9
    assert call_count == 1


def test_rate_date_differs_from_asked_date(monkeypatch):
    app.rate_cache.clear()

    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            # asked for a Saturday, upstream returns Friday's rate
            return FakeResponse(
                200,
                {
                    "amount": 1.0,
                    "base": "EUR",
                    "date": "2026-08-28",  # Friday
                    "rates": {"TRY": 56.1718},
                },
            )

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "250",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-29",  # Saturday — no rate published
        },
    )

    data = response.json()
    assert response.status_code == 200
    assert data["asked_date"] == "2026-08-29"
    assert data["rate_date"] == "2026-08-28"
    assert data["asked_date"] != data["rate_date"]


def test_result_is_rounded_to_two_decimal_places(monkeypatch):
    app.rate_cache.clear()

    async def fake_get_currencies():
        return {"EUR": "Euro", "TRY": "Turkish Lira"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, params=None):
            return FakeResponse(
                200,
                {
                    "amount": 1.0,
                    "base": "EUR",
                    "date": "2026-08-28",
                    "rates": {
                        "TRY": "56.171812345",
                    },
                },
            )

    monkeypatch.setattr(app, "get_currencies", fake_get_currencies)
    monkeypatch.setattr(app.httpx, "AsyncClient", FakeClient)

    response = client.get(
        "/tools/convert",
        params={
            "amount": "333.123456789",
            "from": "EUR",
            "to": "TRY",
            "date": "2026-08-28",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["rate"] == 56.171812345
    assert data["result"] == 18712.15