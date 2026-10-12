import asyncio

import httpx

from backend.app import main


def request_capabilities(client_host, headers=None):
    async def send_request():
        transport = httpx.ASGITransport(
            app=main.app,
            client=(client_host, 12345),
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/mcp/capabilities", headers=headers)

    return asyncio.run(send_request())


def test_remote_request_requires_api_key_when_unconfigured(monkeypatch):
    monkeypatch.setattr(main.settings, "API_KEY", "")

    response = request_capabilities("203.0.113.10")

    assert response.status_code == 503
    assert response.json()["detail"] == "API_KEY must be configured for non-loopback access"


def test_remote_request_requires_valid_api_key(monkeypatch):
    monkeypatch.setattr(main.settings, "API_KEY", "test-secret")

    missing = request_capabilities("203.0.113.10")
    invalid = request_capabilities("203.0.113.10", {"x-api-key": "wrong"})
    valid = request_capabilities("203.0.113.10", {"x-api-key": "test-secret"})
    bearer = request_capabilities(
        "203.0.113.10",
        {"authorization": "Bearer test-secret"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 200
    assert bearer.status_code == 200


def test_loopback_request_remains_available_without_api_key(monkeypatch):
    monkeypatch.setattr(main.settings, "API_KEY", "")

    response = request_capabilities("127.0.0.1")

    assert response.status_code == 200


def test_remote_cors_preflight_is_allowed_without_api_key(monkeypatch):
    monkeypatch.setattr(main.settings, "API_KEY", "test-secret")

    async def send_preflight():
        transport = httpx.ASGITransport(
            app=main.app,
            client=("203.0.113.10", 12345),
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.options(
                "/mcp/capabilities",
                headers={
                    "origin": "http://localhost:3000",
                    "access-control-request-method": "GET",
                },
            )

    response = asyncio.run(send_preflight())

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
