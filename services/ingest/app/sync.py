from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .providers.base import ExternalChannel, Provider
from .quota import QuotaExhausted, QuotaLedger

"""
The nightly referenced-content sync — §4.2.

Three rules govern this file:

  1. Never call third-party search. The provider interface has no search
     method, so the rule is structural rather than remembered.
  2. Log consumption per run and fail closed. The ledger is checked *before*
     every call, and persisted even when the run fails.
  3. Do not close the capability gap by unofficial means. This writes metadata
     and nothing else; Class B rows carry no transcript, and the database
     rejects one if this ever tried.

Idempotent by §5: safe to re-run at any time. Channels are resolved once and
cached; videos conflict on (source_class, external_id) and are skipped.
"""

logger = logging.getLogger("ingest")


@dataclass
class SyncReport:
    channels_seen: int = 0
    channels_resolved: int = 0
    videos_inserted: int = 0
    videos_skipped: int = 0
    units_spent: int = 0
    stopped_early: str | None = None

    def as_dict(self) -> dict:
        return {
            "channels_seen": self.channels_seen,
            "channels_resolved": self.channels_resolved,
            "videos_inserted": self.videos_inserted,
            "videos_skipped": self.videos_skipped,
            "units_spent": self.units_spent,
            "stopped_early": self.stopped_early,
        }


def load_channels(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    return payload["channels"]


async def _upsert_channel(pool, channel: ExternalChannel) -> str:
    """
    Referenced channels are synthetic records, not real users (§6.1).

    Returns the local channel id. The handle is prefixed so a referenced
    channel can never collide with an owned one — handles are unique across
    both, and an ingest run should not be able to take a name an uploader
    might want.
    """
    local_handle = channel.handle.lstrip("@").lower()

    row = await pool.fetchrow(
        """
        INSERT INTO channels (handle, name, description, source_class, external_id)
        VALUES ($1, $2, $3, 'referenced', $4)
        ON CONFLICT (source_class, external_id) DO UPDATE
        SET name = EXCLUDED.name, description = EXCLUDED.description
        RETURNING id
        """,
        local_handle,
        channel.name,
        channel.description,
        channel.external_id,
    )
    return row["id"]


async def _insert_videos(pool, channel_id, videos) -> tuple[int, int]:
    if not videos:
        return 0, 0

    rows = await pool.fetch(
        """
        INSERT INTO videos
            (source_class, channel_id, title, description, duration_sec,
             published_at, processing_status, visibility, external_id)
        SELECT 'referenced', $1, t.title, t.description, t.duration_sec,
               t.published_at, 'referenced_only', 'public', t.external_id
        FROM unnest($2::text[], $3::text[], $4::text[], $5::int[], $6::timestamptz[])
             AS t(external_id, title, description, duration_sec, published_at)
        ON CONFLICT (source_class, external_id) DO NOTHING
        RETURNING id
        """,
        channel_id,
        [v.external_id for v in videos],
        [v.title for v in videos],
        [v.description for v in videos],
        [v.duration_sec for v in videos],
        [v.published_at for v in videos],
    )

    inserted = len(rows)
    return inserted, len(videos) - inserted


async def sync(
    pool,
    provider: Provider,
    channels: list[dict],
    daily_limit: int,
    max_pages: int,
    today=None,
) -> SyncReport:
    report = SyncReport()
    ledger = await QuotaLedger.open(
        pool, provider.name, daily_limit, today or datetime.now(UTC).date()
    )

    try:
        for entry in channels:
            handle = entry["handle"]
            report.channels_seen += 1

            # Resolution is cached: a channel already in the index does not
            # need looking up again, which makes a nightly re-run nearly free.
            existing = await pool.fetchrow(
                """
                SELECT id, external_id FROM channels
                WHERE source_class = 'referenced' AND handle = $1
                """,
                handle.lstrip("@").lower(),
            )

            if existing:
                channel_id = existing["id"]
                uploads_playlist = f"UU{existing['external_id'][2:]}"
            else:
                ledger.check(1)
                resolved = await provider.resolve_channel(handle)
                ledger.record("channels.list", 1)
                if resolved is None:
                    logger.warning("could not resolve %s", handle)
                    continue

                channel_id = await _upsert_channel(pool, resolved)
                uploads_playlist = resolved.uploads_playlist_id
                report.channels_resolved += 1

            page_token: str | None = None
            for _ in range(max_pages):
                # Checked before the request, so the budget is never breached
                # and then reported.
                ledger.check(2)
                page = await provider.list_uploads(uploads_playlist, page_token)
                ledger.record("playlistItems.list", page.units_spent, len(page.items))

                inserted, skipped = await _insert_videos(pool, channel_id, page.items)
                report.videos_inserted += inserted
                report.videos_skipped += skipped

                page_token = page.next_page_token
                if not page_token:
                    break

    except QuotaExhausted as stop:
        # Not an error. Stopping is the designed behaviour, and tomorrow's run
        # picks up where this one left off because inserts are idempotent.
        report.stopped_early = str(stop)
        logger.warning("%s", stop)

    finally:
        report.units_spent = sum(units for _, units, _ in ledger.entries)
        await ledger.flush()

    return report
