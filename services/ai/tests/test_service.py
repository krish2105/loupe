import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.main import app


@pytest.fixture
async def client():
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


class TestCors:
    """
    The web app is a different origin from every service by construction, so a
    missing CORS header does not degrade anything — it breaks every browser
    call completely.

    This was shipped broken and only found by driving the UI: the AI panel, the
    comment composer, the like and save buttons, and the progress writer would
    all have failed identically in a browser. Every one of them had passing
    server-side tests.
    """

    async def test_a_preflight_is_answered(self, client):
        response = await client.options(
            "/v1/videos/00000000-0000-0000-0000-000000000000/ask",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    async def test_an_unlisted_origin_is_not_allowed(self, client):
        response = await client.options(
            "/v1/videos/00000000-0000-0000-0000-000000000000/ask",
            headers={
                "Origin": "https://not-ours.example",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.headers.get("access-control-allow-origin") is None


class TestHealth:
    async def test_it_reports_which_models_are_actually_in_use(self, client):
        response = await client.get("/health")

        assert response.status_code == 200
        body = response.json()
        # Which embedder and which answerer is not a detail — an extractive
        # answerer and a generative one have very different properties, and the
        # service should say which one is answering.
        assert body["embedder"] in {"bge-m3", "hashing-v1"}
        assert body["answerer"] in {"extractive-v1", "gemini-flash"}
