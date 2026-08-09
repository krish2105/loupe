import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.config import settings
from app.main import app


@pytest.fixture
async def client():
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


PAYLOAD = {"VideoLibraryId": 1, "VideoGuid": "abc-guid", "Status": 3}


async def test_webhook_is_closed_when_no_secret_is_configured(client):
    """
    An unset secret must fail closed. Bunny does not sign Stream webhooks, so
    an open endpoint would let anyone mark any video transcoded — and playback
    gates on that status.
    """
    settings.webhook_secret = ""

    response = await client.post("/webhooks/bunny/anything", json=PAYLOAD)

    assert response.status_code == 404


async def test_webhook_rejects_a_wrong_secret(client):
    settings.webhook_secret = "correct-secret"

    response = await client.post("/webhooks/bunny/wrong-secret", json=PAYLOAD)

    assert response.status_code == 404
    settings.webhook_secret = ""


async def test_health_reports_provider_configuration_honestly(client):
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # No credentials in this environment, and the service says so rather than
    # pretending to be ready.
    assert body["provider_configured"] is False
