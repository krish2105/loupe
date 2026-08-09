from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from . import db
from .config import settings
from .providers.fixture import FixtureProvider
from .providers.youtube import YouTubeProvider
from .sync import load_channels, sync

"""
The nightly entry point.

    uv run python -m app.run

Runs against the real Data API when YOUTUBE_API_KEY is set, and the fixture
provider otherwise. Both travel the same path, so the only thing a key changes
is where the metadata comes from.
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ingest")

CHANNELS_FILE = Path(__file__).resolve().parent.parent / "channels.json"


def build_provider():
    if settings.youtube_api_key:
        logger.info("using the YouTube Data API")
        return YouTubeProvider(settings.youtube_api_key)

    logger.info(
        "no YOUTUBE_API_KEY set — using the fixture provider. "
        "Content is generated, deterministic, and labelled as such."
    )
    return FixtureProvider(videos_per_page=50, pages=settings.max_pages_per_channel)


async def main() -> int:
    pool = await db.connect()
    try:
        report = await sync(
            pool,
            build_provider(),
            load_channels(CHANNELS_FILE),
            daily_limit=settings.daily_quota_units,
            max_pages=settings.max_pages_per_channel,
        )
    finally:
        await pool.close()

    print(json.dumps(report.as_dict(), indent=2))

    # A run that stopped on quota is not a failure — it is the designed
    # behaviour, and tomorrow's run resumes. Exit non-zero only if nothing at
    # all was achieved, which is what a monitor should page on.
    if report.videos_inserted == 0 and report.stopped_early:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
