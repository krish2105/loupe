"""
Rewriting HLS playlists so a private bucket can be played.

A public bucket needs none of this: the player fetches the manifest, follows
relative paths, and every segment is readable by anyone who has the URL. That
convenience is exactly the problem. It means a URL, once leaked or cached, works
forever, and a takedown has to delete the object because nothing else can revoke
it. This platform accepts uploads from anyone and owes a removal path that
actually removes things.

So the bucket stays private and the playlists are rewritten on the way out. Our
API fetches the manifest, replaces every URI in it with one the caller is
entitled to, and returns the result. Only the manifest — a few kilobytes — goes
through our infrastructure; the video bytes still travel from bucket to viewer
directly.

The rewriting is pure and knows nothing about signing. It finds URIs and calls
`resolve`; what a URI resolves *to* is the caller's decision, because the two
kinds need opposite treatment:

    a segment    →  a presigned bucket URL, fetched directly
    a playlist   →  back through this endpoint, so its own URIs get rewritten
                    when it is fetched rather than signed now and stale later

Doing that split here would bake the routing into the parser. Leaving it to the
caller keeps this testable with a `resolve` that just returns a marker.
"""

from __future__ import annotations

import re
from collections.abc import Callable

#: Tags carrying a `URI="..."` attribute rather than a bare line.
#:
#: EXT-X-MAP is the fMP4 initialisation segment — miss it and fragmented-MP4
#: streams fail with a decode error rather than a 403, which sends you looking
#: at the transcoder instead of the manifest. EXT-X-MEDIA points at alternate
#: audio and subtitle renditions, EXT-X-KEY at the decryption key, and
#: EXT-X-I-FRAME-STREAM-INF at the trick-play playlist used for scrub previews.
_URI_ATTRIBUTE = re.compile(r'(URI=")([^"]*)(")')


def rewrite(playlist: str, resolve: Callable[[str], str]) -> str:
    """
    Return `playlist` with every URI passed through `resolve`.

    Line endings are normalised to `\\n`. Blank lines and comments survive
    untouched — a comment that is not a tag is still part of the document, and
    players have been known to care about the trailing newline.

    Absolute URLs are left alone. A manifest that already points somewhere
    complete is either not ours to sign or has been rewritten once already, and
    signing it again would corrupt it.
    """
    out: list[str] = []

    for raw in playlist.replace("\r\n", "\n").split("\n"):
        line = raw.strip()

        if not line:
            out.append(raw)
            continue

        if line.startswith("#"):
            # Tags may carry URIs inside attributes. Everything else is prose.
            def substitute(match: re.Match[str]) -> str:
                return match.group(1) + _maybe(match.group(2), resolve) + match.group(3)

            out.append(_URI_ATTRIBUTE.sub(substitute, raw))
            continue

        out.append(_maybe(line, resolve))

    return "\n".join(out)


def _maybe(uri: str, resolve: Callable[[str], str]) -> str:
    """Resolve a URI unless it is already absolute, or empty."""
    if not uri or _is_absolute(uri):
        return uri
    return resolve(uri)


def _is_absolute(uri: str) -> bool:
    lowered = uri.lower()
    return lowered.startswith(("http://", "https://", "//", "data:"))


def is_safe_path(path: str) -> bool:
    """
    Whether a request path can be concatenated into an object key.

    The bucket is private so that access is decided here rather than by whoever
    holds a URL. That decision only holds if the path cannot climb out of the
    prefix it was given — otherwise `../../another-video/hls/master.m3u8` gets
    signed and served, and the private bucket has bought nothing.

    Checked after percent-decoding, which the web framework does before the
    handler sees the value, so `%2e%2e%2f` is already `../` by this point.
    Backslashes are refused too: they are not path separators here, but they are
    on other filesystems, and a key is not worth being clever about.
    """
    if not path or path.startswith("/") or "\\" in path:
        return False
    return ".." not in path.split("/")


def is_playlist(uri: str) -> bool:
    """
    Whether a URI names another playlist rather than a segment.

    Used by callers to decide between routing back through this endpoint and
    presigning the bucket directly. Extension-based, because that is what the
    URI actually tells us — the alternative is fetching it to find out, which
    would mean a request per line of every manifest.

    Query strings are stripped first: a rewritten URI can carry one, and
    `index.m3u8?v=2` is still a playlist.
    """
    path = uri.split("?", 1)[0].split("#", 1)[0]
    return path.lower().endswith((".m3u8", ".m3u"))
