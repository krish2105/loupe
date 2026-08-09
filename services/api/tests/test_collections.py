import uuid

import pytest

from app.routers.collections import COLLECTIONS

from .conftest import token_for


def auth(user_id):
    return {"Authorization": f"Bearer {token_for(user_id)}"}


class TestTheAbstraction:
    """
    The Phase 3 gate: four surfaces from one abstraction, not four one-offs.

    These assert the shape rather than any single surface — if someone later
    adds a fifth collection by writing a bespoke endpoint, the parametrised
    test below stops covering it and the divergence is visible.
    """

    @pytest.mark.parametrize("key", sorted(COLLECTIONS))
    async def test_every_collection_answers_the_same_contract(
        self, client, seeded, key
    ):
        response = await client.get(
            f"/v1/me/collections/{key}", headers=auth(seeded["user_id"])
        )

        assert response.status_code == 200
        body = response.json()
        assert body["key"] == key
        assert isinstance(body["items"], list)
        # Every surface carries its own empty copy, so no caller invents it.
        assert body["empty_title"]
        assert body["empty_body"]

    @pytest.mark.parametrize("key", sorted(COLLECTIONS))
    async def test_every_collection_requires_a_session(self, client, key):
        response = await client.get(f"/v1/me/collections/{key}")
        assert response.status_code == 401

    async def test_an_unknown_collection_is_a_404(self, client, seeded):
        response = await client.get(
            "/v1/me/collections/nonsense", headers=auth(seeded["user_id"])
        )
        assert response.status_code == 404


class TestWatchLater:
    async def test_saving_then_reading_back(self, client, seeded):
        headers = auth(seeded["user_id"])

        saved = await client.put(
            f"/v1/me/saved/watch_later/{seeded['video_id']}", headers=headers
        )
        assert saved.status_code == 204

        listing = await client.get("/v1/me/collections/watch_later", headers=headers)
        assert [item["id"] for item in listing.json()["items"]] == [
            str(seeded["video_id"])
        ]

    async def test_saving_twice_is_a_no_op(self, client, seeded):
        headers = auth(seeded["user_id"])
        path = f"/v1/me/saved/watch_later/{seeded['video_id']}"

        await client.put(path, headers=headers)
        second = await client.put(path, headers=headers)

        # People double-click. The second click must not be an error.
        assert second.status_code == 204

        listing = await client.get("/v1/me/collections/watch_later", headers=headers)
        assert len(listing.json()["items"]) == 1

    async def test_removing_works(self, client, seeded):
        headers = auth(seeded["user_id"])
        path = f"/v1/me/saved/watch_later/{seeded['video_id']}"

        await client.put(path, headers=headers)
        await client.delete(path, headers=headers)

        listing = await client.get("/v1/me/collections/watch_later", headers=headers)
        assert listing.json()["items"] == []

    async def test_watch_later_and_liked_are_separate(self, client, seeded):
        headers = auth(seeded["user_id"])
        await client.put(f"/v1/me/saved/liked/{seeded['video_id']}", headers=headers)

        later = await client.get("/v1/me/collections/watch_later", headers=headers)
        liked = await client.get("/v1/me/collections/liked", headers=headers)

        # One table, two semantics (§6.2) — which only works if the list_type
        # filter is right in both directions.
        assert later.json()["items"] == []
        assert len(liked.json()["items"]) == 1

    async def test_an_unknown_list_is_a_404(self, client, seeded):
        response = await client.put(
            f"/v1/me/saved/bookmarks/{seeded['video_id']}", headers=auth(seeded["user_id"])
        )
        assert response.status_code == 404


class TestHistory:
    async def test_history_collapses_repeat_views_to_one_row(self, client, seeded):
        headers = auth(seeded["user_id"])

        for position in (30, 600, 1200):
            await client.post(
                "/v1/watch-events",
                headers=headers,
                json={
                    "video_id": str(seeded["video_id"]),
                    "position_sec": position,
                    "watch_pct": position / 3600,
                },
            )

        listing = await client.get("/v1/me/collections/history", headers=headers)
        items = listing.json()["items"]

        # Three events, one talk. §6.5 keeps every event; the surface shows the
        # talk once, at its latest position.
        assert len(items) == 1
        assert items[0]["context"]["position_sec"] == 1200

    async def test_history_carries_the_resume_position(self, client, seeded):
        headers = auth(seeded["user_id"])
        await client.post(
            "/v1/watch-events",
            headers=headers,
            json={
                "video_id": str(seeded["video_id"]),
                "position_sec": 742,
                "watch_pct": 0.2,
            },
        )

        listing = await client.get("/v1/me/collections/history", headers=headers)
        assert listing.json()["items"][0]["context"]["position_sec"] == 742


class TestSubscriptions:
    async def test_subscribing_puts_the_channels_talks_in_the_feed(
        self, client, seeded
    ):
        headers = auth(seeded["user_id"])

        await client.put(
            f"/v1/me/subscriptions/{seeded['channel_id']}", headers=headers
        )

        listing = await client.get("/v1/me/collections/subscriptions", headers=headers)
        assert [item["id"] for item in listing.json()["items"]] == [
            str(seeded["video_id"])
        ]

    async def test_unsubscribing_empties_it(self, client, seeded):
        headers = auth(seeded["user_id"])
        path = f"/v1/me/subscriptions/{seeded['channel_id']}"

        await client.put(path, headers=headers)
        await client.delete(path, headers=headers)

        listing = await client.get("/v1/me/collections/subscriptions", headers=headers)
        assert listing.json()["items"] == []

    async def test_subscribing_to_nothing_is_a_404(self, client, seeded):
        response = await client.put(
            f"/v1/me/subscriptions/{uuid.uuid4()}", headers=auth(seeded["user_id"])
        )
        assert response.status_code == 404


class TestPlaylists:
    async def test_create_add_and_read_back_in_order(self, client, seeded, many_videos):
        headers = auth(seeded["user_id"])

        created = await client.post(
            "/v1/me/playlists", headers=headers, json={"title": "Inference internals"}
        )
        assert created.status_code == 201
        playlist_id = created.json()["id"]

        for video_id in many_videos[:3]:
            await client.put(
                f"/v1/me/playlists/{playlist_id}/items/{video_id}", headers=headers
            )

        detail = await client.get(f"/v1/me/playlists/{playlist_id}", headers=headers)
        body = detail.json()

        assert body["title"] == "Inference internals"
        assert body["is_owner"] is True
        # A playlist is an ordering and reads forwards, unlike every other
        # collection, which is newest-first.
        assert [item["id"] for item in body["items"]] == [str(v) for v in many_videos[:3]]

    async def test_an_untitled_playlist_is_refused(self, client, seeded):
        response = await client.post(
            "/v1/me/playlists", headers=auth(seeded["user_id"]), json={"title": "  "}
        )
        assert response.status_code == 422

    async def test_removing_an_item(self, client, seeded, many_videos):
        headers = auth(seeded["user_id"])
        playlist_id = (
            await client.post("/v1/me/playlists", headers=headers, json={"title": "L"})
        ).json()["id"]

        await client.put(
            f"/v1/me/playlists/{playlist_id}/items/{many_videos[0]}", headers=headers
        )
        await client.delete(
            f"/v1/me/playlists/{playlist_id}/items/{many_videos[0]}", headers=headers
        )

        detail = await client.get(f"/v1/me/playlists/{playlist_id}", headers=headers)
        assert detail.json()["items"] == []

    async def test_someone_elses_private_playlist_looks_like_it_does_not_exist(
        self, client, seeded
    ):
        owner_headers = auth(seeded["user_id"])
        playlist_id = (
            await client.post(
                "/v1/me/playlists", headers=owner_headers, json={"title": "Private"}
            )
        ).json()["id"]

        stranger = await client.get(
            f"/v1/me/playlists/{playlist_id}", headers=auth(uuid.uuid4())
        )

        # 404 rather than 403: a 403 confirms the playlist is real.
        assert stranger.status_code == 404

    async def test_a_stranger_cannot_add_to_your_playlist(self, client, seeded, many_videos):
        playlist_id = (
            await client.post(
                "/v1/me/playlists", headers=auth(seeded["user_id"]), json={"title": "Mine"}
            )
        ).json()["id"]

        response = await client.put(
            f"/v1/me/playlists/{playlist_id}/items/{many_videos[0]}",
            headers=auth(uuid.uuid4()),
        )
        assert response.status_code == 404


class TestVideoState:
    async def test_state_reports_all_three_relationships(self, client, seeded):
        headers = auth(seeded["user_id"])

        await client.put(f"/v1/me/saved/liked/{seeded['video_id']}", headers=headers)
        await client.put(f"/v1/me/subscriptions/{seeded['channel_id']}", headers=headers)

        state = await client.get(
            f"/v1/me/state/{seeded['video_id']}", headers=headers
        )
        body = state.json()

        assert body["liked"] is True
        assert body["watch_later"] is False
        assert body["subscribed"] is True

    async def test_one_persons_state_is_not_anothers(self, client, seeded):
        await client.put(
            f"/v1/me/saved/liked/{seeded['video_id']}", headers=auth(seeded["user_id"])
        )

        state = await client.get(
            f"/v1/me/state/{seeded['video_id']}", headers=auth(uuid.uuid4())
        )
        assert state.json()["liked"] is False
