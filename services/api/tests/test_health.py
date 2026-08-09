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


async def test_health_reports_status_without_a_database(client):
    """
    The API must start and answer even when Postgres is unreachable. CI has no
    database in this job, so this also proves the degraded path is real rather
    than theoretical.
    """
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"ok", "error", "unavailable"}


async def test_pipeline_stages_degrades_cleanly(client):
    response = await client.get("/v1/pipeline/stages")

    assert response.status_code == 200
    assert "stages" in response.json()
