from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

"""
The provider interface.

Two implementations travel the same ingest path: the real Data API client and
a fixture generator. That is not a testing convenience — it is what lets the
quota ledger, the idempotency, the capability rules, and the write path all be
exercised without a key, so the only thing unverified when a key arrives is the
HTTP call itself.
"""


@dataclass(frozen=True)
class ExternalChannel:
    external_id: str
    handle: str
    name: str
    description: str | None
    uploads_playlist_id: str


@dataclass(frozen=True)
class ExternalVideo:
    external_id: str
    title: str
    description: str | None
    published_at: datetime
    duration_sec: int | None


@dataclass(frozen=True)
class Page:
    """One API page: the items, the cursor, and what it cost."""

    items: list[ExternalVideo]
    next_page_token: str | None
    units_spent: int


class Provider(Protocol):
    name: str

    async def resolve_channel(self, handle: str) -> ExternalChannel | None:
        """Handle to channel record, including its uploads playlist. Costs 1 unit."""
        ...

    async def list_uploads(
        self, uploads_playlist_id: str, page_token: str | None
    ) -> Page:
        """
        One page of a channel's uploads.

        §4.2 rule 1 is specific: walk the uploads playlist at 1 unit per 50
        items. Search costs 100 units for the same 50 and is forbidden here at
        any time, not merely at runtime.
        """
        ...
