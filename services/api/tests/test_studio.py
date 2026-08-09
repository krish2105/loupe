import uuid

import pytest

from app import db
from app.routers.studio import channel_handle_for

from .conftest import token_for

"""
Creating a video.

The endpoint that the upload flow could not exist without: the media service
issues a ticket against a video id, and until this existed nothing could produce
one. The page invented a UUID and met a foreign key violation, which is the
correct answer to asking a database to attach media to a video nobody created.
"""


def auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(user_id)}"}


class TestHandleDerivation:
    """
    Pure, so it is tested here rather than through eight HTTP round trips.
    Derived rather than asked for: someone uploading a first talk has not
    decided what to call a channel, and making them decide mid-upload is how an
    upload gets abandoned.
    """

    def test_passes_through_an_ordinary_handle(self):
        assert channel_handle_for("krishna") == "krishna"

    def test_lowercases_and_replaces_what_a_handle_may_not_contain(self):
        assert channel_handle_for("Krishna.Mathur_08") == "krishna-mathur-08"

    def test_collapses_runs_and_trims_the_edges(self):
        assert channel_handle_for("--a...b--") == "a-b"

    def test_never_returns_empty(self):
        # A handle of pure punctuation would otherwise put a channel at `/c/`.
        assert channel_handle_for("...") == "channel"
        assert channel_handle_for("") == "channel"


class TestAuthentication:
    async def test_creating_a_video_requires_a_token(self, client):
        response = await client.post("/v1/videos", json={"title": "A talk"})
        assert response.status_code == 401

    async def test_an_expired_token_is_rejected(self, client):
        response = await client.post(
            "/v1/videos",
            headers={"Authorization": f"Bearer {token_for(uuid.uuid4(), expired=True)}"},
            json={"title": "A talk"},
        )
        assert response.status_code == 401


class TestCreatingAVideo:
    async def test_creates_a_private_video_in_a_new_channel(self, client, seeded):
        response = await client.post(
            "/v1/videos",
            headers=auth(seeded["user_id"]),
            json={"title": "  Speculative decoding  ", "description": " Draft models. "},
        )

        assert response.status_code == 201
        body = response.json()

        # Private and unprocessed. A row created here has nothing behind it —
        # no upload, let alone a transcode — so anything public would put an
        # unplayable entry in a feed.
        assert body["visibility"] == "private"
        assert body["processing_status"] == "uploaded"
        assert body["channel_handle"]

        pool = db.pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                "SELECT title, description, source_class::text AS cls FROM videos WHERE id = $1",
                uuid.UUID(body["id"]),
            )

        assert row["title"] == "Speculative decoding"
        assert row["description"] == "Draft models."
        assert row["cls"] == "owned"

    async def test_the_new_channel_belongs_to_the_caller(self, client, seeded):
        response = await client.post(
            "/v1/videos", headers=auth(seeded["user_id"]), json={"title": "A talk"}
        )

        pool = db.pool()
        async with pool.acquire() as connection:
            owner = await connection.fetchval(
                """
                SELECT c.owner_id FROM channels c
                JOIN videos v ON v.channel_id = c.id
                WHERE v.id = $1
                """,
                uuid.UUID(response.json()["id"]),
            )

        assert owner == seeded["user_id"]

    async def test_a_second_upload_reuses_the_same_channel(self, client, seeded):
        """
        One channel per person — 0013 enforces it with a partial unique index,
        so a second creation would raise rather than quietly make another.
        """
        first = await client.post(
            "/v1/videos", headers=auth(seeded["user_id"]), json={"title": "One"}
        )
        second = await client.post(
            "/v1/videos", headers=auth(seeded["user_id"]), json={"title": "Two"}
        )

        assert second.status_code == 201
        assert first.json()["channel_handle"] == second.json()["channel_handle"]

        pool = db.pool()
        async with pool.acquire() as connection:
            count = await connection.fetchval(
                "SELECT count(*) FROM channels WHERE owner_id = $1", seeded["user_id"]
            )
        assert count == 1

    async def test_two_people_with_colliding_handles_both_get_a_channel(
        self, client, seeded
    ):
        """
        The suffix path. Two users whose handles reduce to the same slug — a
        realistic collision once handles allow punctuation the channel handle
        does not.
        """
        pool = db.pool()
        other_id = uuid.uuid4()
        shared = f"u-{uuid.uuid4().hex[:8]}"

        async with pool.acquire() as connection:
            await connection.execute(
                "UPDATE users SET handle = $2 WHERE id = $1", seeded["user_id"], shared
            )
            await connection.execute(
                "INSERT INTO users (id, handle, display_name) VALUES ($1, $2, $3)",
                other_id,
                shared.replace("-", "."),  # different handle, same slug
                "Other Person",
            )

        first = await client.post(
            "/v1/videos", headers=auth(seeded["user_id"]), json={"title": "One"}
        )
        second = await client.post(
            "/v1/videos", headers=auth(other_id), json={"title": "Two"}
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["channel_handle"] != second.json()["channel_handle"]

    async def test_a_caller_with_no_profile_row_gets_an_explanation(self, client):
        """
        Real state, not a defensive branch: a token verifies because the account
        exists upstream, while the local profile row has not been written yet.
        A 500 here would read as a broken service rather than a moment to wait.
        """
        pool = db.pool()
        if pool is None:
            pytest.skip("No database available")

        response = await client.post(
            "/v1/videos", headers=auth(uuid.uuid4()), json={"title": "A talk"}
        )

        assert response.status_code == 409
        assert "profile" in response.json()["detail"].lower()

    async def test_a_blank_title_is_refused(self, client, seeded):
        response = await client.post(
            "/v1/videos", headers=auth(seeded["user_id"]), json={"title": ""}
        )
        assert response.status_code == 422
