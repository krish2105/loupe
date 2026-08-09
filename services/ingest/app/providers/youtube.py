from __future__ import annotations

import re
from datetime import datetime

import httpx

from .base import ExternalChannel, ExternalVideo, Page

"""
The YouTube Data API provider.

§4.2 rule 1, stated exactly: never call search. A search call costs 100 units
and returns the same 50 items a playlistItems call returns for 1 — a factor of
a hundred, which is the whole reason the plan forbids it rather than merely
discouraging it. There is no code path here that can reach search.

Costs, per the published quota table:
    channels.list        1 unit
    playlistItems.list   1 unit per page of 50
    videos.list          1 unit per page of 50 (durations only)
"""

API_BASE = "https://www.googleapis.com/youtube/v3"

# PT1H2M10S
_DURATION = re.compile(
    r"P(?:(?P<days>\d+)D)?T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?"
)


def parse_duration(value: str | None) -> int | None:
    """ISO 8601 duration to seconds. Returns None rather than guessing."""
    if not value:
        return None
    match = _DURATION.fullmatch(value)
    if not match:
        return None

    parts = match.groupdict()
    return (
        int(parts["days"] or 0) * 86400
        + int(parts["h"] or 0) * 3600
        + int(parts["m"] or 0) * 60
        + int(parts["s"] or 0)
    )


class YouTubeProvider:
    name = "youtube"

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client

    async def _get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self._api_key}
        if self._client is not None:
            response = await self._client.get(f"{API_BASE}/{path}", params=params)
        else:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(f"{API_BASE}/{path}", params=params)
        response.raise_for_status()
        return response.json()

    async def resolve_channel(self, handle: str) -> ExternalChannel | None:
        payload = await self._get(
            "channels",
            {
                "part": "snippet,contentDetails",
                "forHandle": handle if handle.startswith("@") else f"@{handle}",
            },
        )

        items = payload.get("items") or []
        if not items:
            return None

        item = items[0]
        return ExternalChannel(
            external_id=item["id"],
            handle=handle,
            name=item["snippet"]["title"],
            description=item["snippet"].get("description"),
            uploads_playlist_id=item["contentDetails"]["relatedPlaylists"]["uploads"],
        )

    async def list_uploads(
        self, uploads_playlist_id: str, page_token: str | None
    ) -> Page:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": uploads_playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        payload = await self._get("playlistItems", params)
        units = 1

        entries = []
        for item in payload.get("items", []):
            snippet = item["snippet"]
            video_id = item["contentDetails"]["videoId"]
            entries.append((video_id, snippet))

        durations: dict[str, int | None] = {}
        if entries:
            # One more unit buys durations for the whole page. Worth it: a card
            # without a runtime is noticeably worse, and the alternative is a
            # per-video call, which would be fifty times the cost.
            detail = await self._get(
                "videos",
                {"part": "contentDetails", "id": ",".join(v for v, _ in entries)},
            )
            units += 1
            for item in detail.get("items", []):
                durations[item["id"]] = parse_duration(
                    item["contentDetails"].get("duration")
                )

        videos = [
            ExternalVideo(
                external_id=video_id,
                title=snippet["title"],
                description=snippet.get("description"),
                published_at=datetime.fromisoformat(
                    snippet["publishedAt"].replace("Z", "+00:00")
                ),
                duration_sec=durations.get(video_id),
            )
            for video_id, snippet in entries
        ]

        return Page(
            items=videos,
            next_page_token=payload.get("nextPageToken"),
            units_spent=units,
        )
