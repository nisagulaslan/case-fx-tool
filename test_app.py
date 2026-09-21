from fastapi.testclient import TestClient

import app


client = TestClient(app.app)


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