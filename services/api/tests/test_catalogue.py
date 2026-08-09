import uuid

from app import db

from .conftest import token_for


class TestCapabilities:
    """
    §4's capability matrix, as the API reports it.

    These are the flags every unavailable state in the UI is built from, so a
    silent change here would quietly re-enable AI affordances on content that
    has no transcript.
    """

    async def test_an_indexed_owned_talk_can_do_everything(self, client, seeded):
        response = await client.get(f"/v1/videos/{seeded['video_id']}")

        assert response.status_code == 200
        capabilities = response.json()["capabilities"]
        assert capabilities["playable"] is True
        assert capabilities["searchable_inside"] is True
        assert capabilities["askable"] is True
        assert capabilities["processing"] is False

    async def test_a_referenced_talk_can_do_none_of_it(self, client, referenced_video):
        response = await client.get(f"/v1/videos/{referenced_video}")

        assert response.status_code == 200
        body = response.json()
        assert body["source_class"] == "referenced"
        assert body["capabilities"]["playable"] is False
        assert body["capabilities"]["askable"] is False
        assert body["capabilities"]["searchable_inside"] is False
        # No custom playback for Class B — §9.1 swaps to the third-party embed.
        assert body["hls_url"] is None

    async def test_a_talk_mid_pipeline_is_not_yet_askable(self, client, processing_video):
        response = await client.get(f"/v1/videos/{processing_video}")

        capabilities = response.json()["capabilities"]
        assert capabilities["processing"] is True
        assert capabilities["askable"] is False
        # §5.1: watchable long before it is searchable.
        assert capabilities["playable"] is True

    async def test_an_unknown_talk_is_a_404(self, client, seeded):
        response = await client.get(f"/v1/videos/{uuid.uuid4()}")
        assert response.status_code == 404


class TestFeed:
    async def test_the_feed_returns_items_with_capabilities(self, client, seeded):
        response = await client.get("/v1/feed?limit=5")

        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) > 0
        for item in body["items"]:
            assert "capabilities" in item
            assert "channel" in item

    async def test_pagination_never_repeats_or_skips(self, client, many_videos):
        first = await client.get("/v1/feed?limit=3")
        cursor = first.json()["next_cursor"]
        assert cursor is not None

        second = await client.get(f"/v1/feed?limit=3&cursor={cursor}")

        first_ids = [item["id"] for item in first.json()["items"]]
        second_ids = [item["id"] for item in second.json()["items"]]

        # The failure keyset pagination exists to prevent: with OFFSET, a row
        # inserted between the two requests shifts everything and an item is
        # served twice or never.
        assert set(first_ids).isdisjoint(second_ids)

    async def test_a_corrupt_cursor_is_a_client_error(self, client, seeded):
        response = await client.get("/v1/feed?cursor=not-a-real-cursor")
        assert response.status_code == 400


class TestChannel:
    async def test_a_channel_lists_its_own_uploads(self, client, seeded):
        async with db.pool().acquire() as connection:
            handle = await connection.fetchval(
                "SELECT handle FROM channels WHERE id = $1", seeded["channel_id"]
            )

        response = await client.get(f"/v1/channels/{handle}")

        assert response.status_code == 200
        body = response.json()
        assert body["channel"]["handle"] == handle
        assert [v["id"] for v in body["videos"]] == [str(seeded["video_id"])]

    async def test_an_unknown_channel_is_a_404(self, client, seeded):
        response = await client.get("/v1/channels/nobody-here")
        assert response.status_code == 404


class TestComments:
    def auth(self, user_id):
        return {"Authorization": f"Bearer {token_for(user_id)}"}

    async def test_posting_requires_a_session(self, client, seeded):
        response = await client.post(
            f"/v1/videos/{seeded['video_id']}/comments", json={"body": "hello"}
        )
        assert response.status_code == 401

    async def test_a_comment_and_its_reply_nest(self, client, seeded):
        top = await client.post(
            f"/v1/videos/{seeded['video_id']}/comments",
            headers=self.auth(seeded["user_id"]),
            json={"body": "The roofline section was the useful part."},
        )
        assert top.status_code == 201
        parent_id = top.json()["id"]

        reply = await client.post(
            f"/v1/videos/{seeded['video_id']}/comments",
            headers=self.auth(seeded["user_id"]),
            json={"body": "Agreed.", "parent_id": parent_id},
        )
        assert reply.status_code == 201

        listing = await client.get(f"/v1/videos/{seeded['video_id']}/comments")
        threads = listing.json()["items"]

        assert len(threads) == 1
        assert len(threads[0]["replies"]) == 1
        assert threads[0]["replies"][0]["body"] == "Agreed."

    async def test_a_reply_to_a_reply_is_refused(self, client, seeded):
        """
        §6.2 allows one reply level. The database enforces it; this asserts the
        API turns that into something a person can act on rather than a 500.
        """
        top = await client.post(
            f"/v1/videos/{seeded['video_id']}/comments",
            headers=self.auth(seeded["user_id"]),
            json={"body": "top"},
        )
        reply = await client.post(
            f"/v1/videos/{seeded['video_id']}/comments",
            headers=self.auth(seeded["user_id"]),
            json={"body": "reply", "parent_id": top.json()["id"]},
        )

        nested = await client.post(
            f"/v1/videos/{seeded['video_id']}/comments",
            headers=self.auth(seeded["user_id"]),
            json={"body": "reply to reply", "parent_id": reply.json()["id"]},
        )

        assert nested.status_code == 422
        assert "one level" in nested.json()["detail"]

    async def test_an_empty_comment_is_refused(self, client, seeded):
        response = await client.post(
            f"/v1/videos/{seeded['video_id']}/comments",
            headers=self.auth(seeded["user_id"]),
            json={"body": "   "},
        )
        # A whitespace-only body must be rejected as validation, not surface as
        # a database CHECK violation the caller cannot interpret.
        assert response.status_code == 422

    async def test_the_comment_count_keeps_up(self, client, seeded):
        await client.post(
            f"/v1/videos/{seeded['video_id']}/comments",
            headers=self.auth(seeded["user_id"]),
            json={"body": "counted"},
        )

        detail = await client.get(f"/v1/videos/{seeded['video_id']}")
        assert detail.json()["comment_count"] == 1
