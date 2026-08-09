from __future__ import annotations

"""
Turning a stored asset reference into something a player can open.

`video_assets.hls_url` holds two different kinds of thing, and it has to,
because the platform serves two kinds of media.

    an absolute URL   the seeded catalogue's public reference stream, and
                      anything a provider hosts and addresses itself

    a bucket key      `videos/<id>/hls/master.m3u8`, produced by our own
                      transcoder. Not a URL and not meant to be — the bucket is
                      private, so the object is only reachable through the media
                      service, which signs each playlist on request

Storing the key rather than a URL is deliberate. A URL would bake the media
service's hostname into every row, so moving the service would mean rewriting
the table, and a signed URL would be worse still because it would expire in
place. The row records *what* the asset is; each service renders *where* at the
moment it answers.

Which leaves this: one function, so the four endpoints that return `hls_url` do
not each invent their own answer.
"""


def playable_url(stored: str | None, media_service_url: str) -> str | None:
    """
    A URL a player can open, or None if there is nothing to open.

    An absolute reference passes through untouched. A key becomes a media
    service address. Anything else — an empty string, a stray whitespace-only
    value — becomes None rather than a URL that resolves against the web app's
    own origin and 404s there, which is a confusing way to learn the column was
    blank.

    With no media service configured a key returns None, because a key alone
    cannot be opened by anything. The alternative is handing the player a
    relative path and letting it fail somewhere less obvious.
    """
    reference = (stored or "").strip()
    if not reference:
        return None

    if reference.startswith(("http://", "https://", "//")):
        return reference

    base = media_service_url.strip().rstrip("/")
    if not base:
        return None

    # The stored key is `videos/<id>/hls/<tail>`; the media service's route is
    # `/v1/hls/<id>/<tail>` and rebuilds the key itself. Prefixing the whole key
    # produces `/v1/hls/videos/<id>/hls/...`, which the route reads as
    # id="videos" and then looks for `videos/videos/<id>/hls/...` — a 404 that
    # looks like missing media rather than a malformed URL.
    parts = reference.lstrip("/").split("/")
    if len(parts) >= 4 and parts[0] == "videos" and parts[2] == "hls":
        return f"{base}/v1/hls/{parts[1]}/{'/'.join(parts[3:])}"

    # An unrecognised shape is not ours to route. Better None than a URL built
    # on a guess about a layout that has changed.
    return None
