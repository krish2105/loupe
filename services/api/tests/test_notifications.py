import uuid

import pytest

from app import db
from tests.conftest import token_for

"""
Notification fan-out (§6.2, migration 0009).

The fan-out lives in database triggers, so these tests write rows directly and
assert on what appears — that is the actual contract. Testing it through the API
would only prove the router can read a table.
"""


@pytest.fixture
async def subscriber(seeded):
    """Someone following the seeded channel, subscribed as of now."""
    pool = db.pool()
    if pool is None:
        pytest.skip("No database available")

    user_id = uuid.uuid4()
    async with pool.acquire() as connection:
        await connection.execute(
            "INSERT INTO users (id, handle, display_name) VALUES ($1, $2, 'Follower')",
            user_id,
            f"f-{user_id.hex[:8]}",
        )
        await connection.execute(
            "INSERT INTO subscriptions (user_id, channel_id) VALUES ($1, $2)",
            user_id,
            seeded["channel_id"],
        )

    yield user_id

    async with pool.acquire() as connection:
        await connection.execute("DELETE FROM users WHERE id = $1", user_id)


async def publish(connection, channel_id, *, published_at: str, status="transcoded"):
    video_id = uuid.uuid4()
    await connection.execute(
        f"""
        INSERT INTO videos
            (id, source_class, channel_id, title, processing_status, published_at)
        VALUES ($1, 'owned', $2, 'A new talk', '{status}', {published_at})
        """,
        video_id,
        channel_id,
    )
    return video_id


async def notification_count(connection, user_id, video_id) -> int:
    return await connection.fetchval(
        "SELECT count(*) FROM notifications WHERE user_id = $1 AND target_id = $2",
        user_id,
        video_id,
    )


class TestNewUploadFanOut:
    async def test_a_subscriber_is_notified(self, seeded, subscriber):
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection, seeded["channel_id"], published_at="now()"
            )
            assert await notification_count(connection, subscriber, video_id) == 1
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

    async def test_the_back_catalogue_does_not_notify(self, seeded, subscriber):
        """
        You hear about talks posted after you followed, not everything the
        channel ever published.

        This is the semantics a viewer expects, and it is also what stops the
        Class B backfill — three thousand historical videos inserted in one
        nightly run — from generating a notification per subscriber per row.
        """
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection,
                seeded["channel_id"],
                published_at="now() - interval '30 days'",
            )
            assert await notification_count(connection, subscriber, video_id) == 0
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

    async def test_republishing_does_not_notify_twice(self, seeded, subscriber):
        """
        §5.1 idempotency. A transcode retried after a failure re-enters
        'transcoded', and telling someone about the same talk twice is the
        specific way a notification feed loses trust.
        """
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection, seeded["channel_id"], published_at="now()"
            )
            await connection.execute(
                "UPDATE videos SET processing_status = 'failed_transcoding' WHERE id = $1",
                video_id,
            )
            await connection.execute(
                "UPDATE videos SET processing_status = 'transcoded' WHERE id = $1",
                video_id,
            )

            assert await notification_count(connection, subscriber, video_id) == 1
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

    async def test_an_unwatchable_video_does_not_notify(self, seeded, subscriber):
        """A talk still transcoding cannot be watched, so there is nothing to say."""
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection,
                seeded["channel_id"],
                published_at="now()",
                status="transcoding",
            )
            assert await notification_count(connection, subscriber, video_id) == 0

            # ...and it does notify once it becomes watchable.
            await connection.execute(
                "UPDATE videos SET processing_status = 'transcoded' WHERE id = $1",
                video_id,
            )
            assert await notification_count(connection, subscriber, video_id) == 1
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

    async def test_a_failed_transcript_still_notifies(self, seeded, subscriber):
        """
        The talk plays; what failed is the intelligence layer. Withholding the
        notification would hide a watchable video because a downstream stage
        broke.
        """
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection,
                seeded["channel_id"],
                published_at="now()",
                status="failed_transcribing",
            )
            assert await notification_count(connection, subscriber, video_id) == 1
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

    async def test_a_private_video_does_not_notify(self, seeded, subscriber):
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection, seeded["channel_id"], published_at="now()"
            )
            await connection.execute("DELETE FROM notifications WHERE target_id = $1", video_id)
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

            private_id = uuid.uuid4()
            await connection.execute(
                """
                INSERT INTO videos
                    (id, source_class, channel_id, title, processing_status,
                     visibility, published_at)
                VALUES ($1, 'owned', $2, 'Draft', 'transcoded', 'private', now())
                """,
                private_id,
                seeded["channel_id"],
            )
            assert await notification_count(connection, subscriber, private_id) == 0
            await connection.execute("DELETE FROM videos WHERE id = $1", private_id)

    async def test_a_title_edit_does_not_re_notify(self, seeded, subscriber):
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection, seeded["channel_id"], published_at="now()"
            )
            await connection.execute(
                "UPDATE videos SET title = 'Renamed' WHERE id = $1", video_id
            )
            assert await notification_count(connection, subscriber, video_id) == 1
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

    async def test_muting_a_channel_stops_the_fan_out(self, seeded, subscriber):
        pool = db.pool()
        async with pool.acquire() as connection:
            await connection.execute(
                """
                UPDATE subscriptions SET notify_enabled = false
                WHERE user_id = $1 AND channel_id = $2
                """,
                subscriber,
                seeded["channel_id"],
            )
            video_id = await publish(
                connection, seeded["channel_id"], published_at="now()"
            )
            assert await notification_count(connection, subscriber, video_id) == 0
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)


class TestReplyFanOut:
    async def test_a_reply_notifies_the_parent_author(self, seeded):
        pool = db.pool()
        replier = uuid.uuid4()

        async with pool.acquire() as connection:
            await connection.execute(
                "INSERT INTO users (id, handle, display_name) VALUES ($1, $2, 'Replier')",
                replier,
                f"r-{replier.hex[:8]}",
            )
            parent_id = await connection.fetchval(
                """
                INSERT INTO comments (video_id, user_id, body)
                VALUES ($1, $2, 'The bit at 14:20 is the whole talk') RETURNING id
                """,
                seeded["video_id"],
                seeded["user_id"],
            )
            await connection.execute(
                """
                INSERT INTO comments (video_id, user_id, parent_id, body)
                VALUES ($1, $2, $3, 'Agreed')
                """,
                seeded["video_id"],
                replier,
                parent_id,
            )

            row = await connection.fetchrow(
                """
                SELECT kind::text AS kind, actor_id, target_id
                FROM notifications WHERE user_id = $1 AND kind = 'reply'
                """,
                seeded["user_id"],
            )
            assert row["kind"] == "reply"
            assert row["actor_id"] == replier
            # The video, not the comment — there is no comment permalink to send
            # anyone to.
            assert row["target_id"] == seeded["video_id"]

            await connection.execute("DELETE FROM users WHERE id = $1", replier)

    async def test_replying_to_yourself_is_not_news(self, seeded):
        pool = db.pool()
        async with pool.acquire() as connection:
            parent_id = await connection.fetchval(
                """
                INSERT INTO comments (video_id, user_id, body)
                VALUES ($1, $2, 'First') RETURNING id
                """,
                seeded["video_id"],
                seeded["user_id"],
            )
            await connection.execute(
                """
                INSERT INTO comments (video_id, user_id, parent_id, body)
                VALUES ($1, $2, $3, 'Also me')
                """,
                seeded["video_id"],
                seeded["user_id"],
                parent_id,
            )

            count = await connection.fetchval(
                "SELECT count(*) FROM notifications WHERE user_id = $1 AND kind = 'reply'",
                seeded["user_id"],
            )
            assert count == 0


class TestReadState:
    async def test_opening_the_page_clears_the_badge(
        self, client, seeded, subscriber
    ):
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection, seeded["channel_id"], published_at="now()"
            )

        headers = {"Authorization": f"Bearer {token_for(subscriber)}"}

        before = await client.get("/v1/me/notifications", headers=headers)
        assert before.json()["unread"] == 1

        marked = await client.post("/v1/me/notifications/read", headers=headers)
        assert marked.json()["marked_read"] == 1

        after = await client.get("/v1/me/notifications", headers=headers)
        assert after.json()["unread"] == 0
        assert after.json()["items"][0]["read"] is True

        async with pool.acquire() as connection:
            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)

    async def test_it_requires_a_session(self, client):
        assert (await client.post("/v1/me/notifications/read")).status_code == 401


class TestOrphans:
    async def test_deleting_a_video_takes_its_notifications_with_it(
        self, seeded, subscriber
    ):
        """
        target_id is polymorphic, so it carries no foreign key and gets no
        cascade. Without the purge trigger a deleted talk leaves a row that
        renders with no title and counts toward the unread badge forever.
        """
        pool = db.pool()
        async with pool.acquire() as connection:
            video_id = await publish(
                connection, seeded["channel_id"], published_at="now()"
            )
            assert await notification_count(connection, subscriber, video_id) == 1

            await connection.execute("DELETE FROM videos WHERE id = $1", video_id)
            assert await notification_count(connection, subscriber, video_id) == 0
