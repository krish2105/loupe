from app import db
from tests.conftest import token_for

"""
Download records (ADR 0003, migration 0012).

The bytes live in the browser. These rows are the record of what was asked for
and how big it turned out, and the one rule worth enforcing is that Class B
content can never appear in them.
"""


class TestRecording:
    async def test_it_records_a_download(self, client, seeded):
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.put(
            f"/v1/me/downloads/{seeded['video_id']}", json={}, headers=headers
        )
        assert response.status_code == 204

        listing = await client.get("/v1/me/collections/downloads", headers=headers)
        assert [item["id"] for item in listing.json()["items"]] == [
            str(seeded["video_id"])
        ]

    async def test_completing_a_download_records_its_size(self, client, seeded):
        """
        Two calls per download: one when it starts with no size, one when it
        finishes with one. A null size means "started and never finished", which
        is what lets the UI offer a retry instead of showing a download that
        does not work.
        """
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        await client.put(f"/v1/me/downloads/{seeded['video_id']}", json={}, headers=headers)
        await client.put(
            f"/v1/me/downloads/{seeded['video_id']}",
            json={"bytes": 12_132_238},
            headers=headers,
        )

        pool = db.pool()
        async with pool.acquire() as connection:
            size = await connection.fetchval(
                "SELECT bytes FROM downloads WHERE user_id = $1 AND video_id = $2",
                seeded["user_id"],
                seeded["video_id"],
            )
        assert size == 12_132_238

    async def test_a_restart_does_not_erase_a_recorded_size(self, client, seeded):
        """
        The start call carries no size. Written naively it would null out the
        size of a download that had already completed, which is how a working
        download starts reporting itself as broken.
        """
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        await client.put(
            f"/v1/me/downloads/{seeded['video_id']}",
            json={"bytes": 5_000},
            headers=headers,
        )
        await client.put(f"/v1/me/downloads/{seeded['video_id']}", json={}, headers=headers)

        pool = db.pool()
        async with pool.acquire() as connection:
            size = await connection.fetchval(
                "SELECT bytes FROM downloads WHERE user_id = $1 AND video_id = $2",
                seeded["user_id"],
                seeded["video_id"],
            )
        assert size == 5_000

    async def test_removing_a_download(self, client, seeded):
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        await client.put(f"/v1/me/downloads/{seeded['video_id']}", json={}, headers=headers)
        assert (
            await client.delete(
                f"/v1/me/downloads/{seeded['video_id']}", headers=headers
            )
        ).status_code == 204

        listing = await client.get("/v1/me/collections/downloads", headers=headers)
        assert listing.json()["items"] == []


class TestTheRule:
    async def test_referenced_content_cannot_be_downloaded(
        self, client, seeded, referenced_video
    ):
        """
        ADR 0003: offline works only for content Loupe owns. Class B is
        referenced rather than stored, so there is nothing to cache and no right
        to cache it.

        Enforced by a database trigger, so this holds for anything that writes
        the table rather than for anything that happens to go through this
        endpoint.
        """
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.put(
            f"/v1/me/downloads/{referenced_video}",
            json={},
            headers=headers,
        )

        assert response.status_code == 409
        assert "hosted elsewhere" in response.json()["detail"]

    async def test_an_unknown_talk_is_a_404(self, client, seeded):
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        response = await client.put(
            "/v1/me/downloads/00000000-0000-4000-a000-0000000000ff",
            json={},
            headers=headers,
        )
        assert response.status_code == 404

    async def test_it_requires_a_session(self, client, seeded):
        response = await client.put(f"/v1/me/downloads/{seeded['video_id']}", json={})
        assert response.status_code == 401


class TestTheCollection:
    async def test_downloads_is_a_declared_collection_not_a_special_case(
        self, client, seeded
    ):
        """
        §6.2 claimed in Phase 0 that a fifth surface would cost a dictionary
        entry. Downloads is the first surface the abstraction was not designed
        against, so this asserts it went through the same path as the other
        four rather than around it.
        """
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        listing = await client.get("/v1/me/collections", headers=headers)
        keys = [entry["key"] for entry in listing.json()["collections"]]

        assert "downloads" in keys

    async def test_the_size_rides_along_as_membership_context(self, client, seeded):
        headers = {"Authorization": f"Bearer {token_for(seeded['user_id'])}"}

        await client.put(
            f"/v1/me/downloads/{seeded['video_id']}",
            json={"bytes": 4_096},
            headers=headers,
        )

        listing = await client.get("/v1/me/collections/downloads", headers=headers)
        assert listing.json()["items"][0]["context"]["bytes"] == 4_096
