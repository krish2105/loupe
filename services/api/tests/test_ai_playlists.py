import uuid

import httpx
import pytest

from app import db
from app.routers import collections
from tests.conftest import token_for

"""
AI playlist persistence (§11).

The composition itself is tested in the AI service, where it lives. What this
service owns is the boundary: authorise the caller, call across, write the rows
in one transaction, and translate a refusal into something a client can render.
So the AI service is stubbed here — running it for real would test the wrong
half and make these tests depend on an embedding model.
"""


class StubAI:
    """Stands in for the AI service's compose endpoint."""

    def __init__(self, payload=None, *, status=200, raises=False):
        self.payload = payload
        self.status = status
        self.raises = raises
        self.request_json = None

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        if self.raises:
            raise httpx.ConnectError("refused")
        self.request_json = json
        return httpx.Response(self.status, json=self.payload)


def proposal(video_ids):
    return {
        "refused": False,
        "title": "Attention and long context",
        "rationale": "3 talks from 3 channels, chosen by searching transcripts.",
        "items": [
            {
                "video_id": str(video_id),
                "title": f"Talk {index}",
                "channel_name": "A channel",
                "start_sec": 120.5 + index,
                "excerpt": "The bit where she explains it.",
                "score": 0.7 - index * 0.05,
            }
            for index, video_id in enumerate(video_ids)
        ],
    }


@pytest.fixture
def stub(monkeypatch):
    def install(ai: StubAI):
        monkeypatch.setattr(collections.httpx, "AsyncClient", ai)
        return ai

    return install


async def cleanup(user_id):
    pool = db.pool()
    async with pool.acquire() as connection:
        await connection.execute("DELETE FROM playlists WHERE owner_id = $1", user_id)


class TestComposition:
    async def test_it_saves_a_real_playlist(self, client, seeded, many_videos, stub):
        """
        §11's cache policy for this feature is literally "saved as a real
        playlist" — not a transient response the UI holds until reload.
        """
        ids = many_videos[:3]
        stub(StubAI(proposal(ids)))
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.post(
            "/v1/me/playlists/compose",
            json={"brief": "how attention scales with context length"},
            headers=headers,
        )

        assert response.status_code == 201
        body = response.json()
        assert body["refused"] is False
        assert body["item_count"] == 3

        detail = await client.get(f"/v1/me/playlists/{body['id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["generated_by"] == "ai"
        assert detail.json()["rationale"]
        assert [item["id"] for item in detail.json()["items"]] == [str(i) for i in ids]

        await cleanup(seeded["user_id"])

    async def test_the_matched_moment_is_stored_per_item(
        self, client, seeded, many_videos, stub
    ):
        """
        Without this the playlist is a saved search — a list of titles that
        happen to be related. The start position is what makes it a transcript
        feature.
        """
        ids = many_videos[:3]
        stub(StubAI(proposal(ids)))
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        await client.post(
            "/v1/me/playlists/compose",
            json={"brief": "how attention scales with context length"},
            headers=headers,
        )

        pool = db.pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT pi.start_sec, pi.note
                FROM playlist_items pi
                JOIN playlists p ON p.id = pi.playlist_id
                WHERE p.owner_id = $1 ORDER BY pi.position
                """,
                seeded["user_id"],
            )

        assert [row["start_sec"] for row in rows] == [120, 121, 122]
        assert all(row["note"] for row in rows)

        await cleanup(seeded["user_id"])

    async def test_a_refusal_is_a_success_not_an_error(self, client, seeded, stub):
        """
        "Nothing covers this well enough" is a correct answer to the brief. A
        4xx would make the client render it as a fault and hide the reason.
        """
        stub(StubAI({"refused": True, "reason": "Not enough talks address this."}))
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.post(
            "/v1/me/playlists/compose",
            json={"brief": "underwater basket weaving techniques"},
            headers=headers,
        )

        assert response.status_code == 201
        assert response.json()["refused"] is True
        assert response.json()["reason"]

        # And nothing was written.
        pool = db.pool()
        async with pool.acquire() as connection:
            count = await connection.fetchval(
                "SELECT count(*) FROM playlists WHERE owner_id = $1", seeded["user_id"]
            )
        assert count == 0

    async def test_a_partial_write_leaves_no_playlist(
        self, client, seeded, many_videos, stub
    ):
        """
        One unknown video in the proposal must not leave a playlist whose stored
        rationale describes talks it does not contain. The whole insert is one
        transaction for exactly this.
        """
        ids = [*many_videos[:2], uuid.uuid4()]
        stub(StubAI(proposal(ids)))
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.post(
            "/v1/me/playlists/compose",
            json={"brief": "how attention scales with context length"},
            headers=headers,
        )

        # Retrieval and this write are separate queries against a catalogue the
        # nightly ingest edits, so this is a real race with a retryable answer.
        assert response.status_code == 409

        pool = db.pool()
        async with pool.acquire() as connection:
            count = await connection.fetchval(
                "SELECT count(*) FROM playlists WHERE owner_id = $1", seeded["user_id"]
            )
        assert count == 0


class TestBoundary:
    async def test_the_ai_service_being_down_is_a_503(self, client, seeded, stub):
        stub(StubAI(raises=True))
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.post(
            "/v1/me/playlists/compose",
            json={"brief": "how attention scales with context length"},
            headers=headers,
        )

        assert response.status_code == 503

    async def test_an_upstream_error_is_a_502_not_a_500(self, client, seeded, stub):
        stub(StubAI({"detail": "boom"}, status=500))
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.post(
            "/v1/me/playlists/compose",
            json={"brief": "how attention scales with context length"},
            headers=headers,
        )

        assert response.status_code == 502

    async def test_it_requires_a_session(self, client):
        response = await client.post(
            "/v1/me/playlists/compose", json={"brief": "a reasonable brief"}
        )
        assert response.status_code == 401

    async def test_a_one_word_brief_is_rejected_before_the_call(self, client, seeded, stub):
        ai = stub(StubAI(proposal([])))
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.post(
            "/v1/me/playlists/compose", json={"brief": "scaling"}, headers=headers
        )

        assert response.status_code == 422
        # Validation happens here, so the AI service is never troubled with it.
        assert ai.request_json is None
