from app.playlist import is_playlist, is_safe_path, rewrite

"""
Playlist rewriting.

`resolve` is a marker in almost every test. What a URI becomes is the caller's
decision and is tested where that decision lives; what matters here is that
every URI is found and nothing else is touched.
"""


def mark(uri: str) -> str:
    return f"<{uri}>"


def test_rewrites_bare_segment_lines():
    playlist = "\n".join(
        [
            "#EXTM3U",
            "#EXT-X-TARGETDURATION:6",
            "#EXTINF:6.0,",
            "seg-00001.ts",
            "#EXTINF:6.0,",
            "seg-00002.ts",
            "#EXT-X-ENDLIST",
        ]
    )

    assert rewrite(playlist, mark).splitlines() == [
        "#EXTM3U",
        "#EXT-X-TARGETDURATION:6",
        "#EXTINF:6.0,",
        "<seg-00001.ts>",
        "#EXTINF:6.0,",
        "<seg-00002.ts>",
        "#EXT-X-ENDLIST",
    ]


def test_rewrites_the_fmp4_initialisation_segment():
    """
    EXT-X-MAP is a URI hiding in an attribute, and it is the one most easily
    missed. A fragmented-MP4 stream whose init segment 403s does not report a
    permissions problem — it reports a decode failure, which sends you to the
    transcoder rather than the manifest.
    """
    playlist = '#EXT-X-MAP:URI="init.mp4"\n#EXTINF:6.0,\nseg-00001.m4s'

    assert rewrite(playlist, mark).splitlines() == [
        '#EXT-X-MAP:URI="<init.mp4>"',
        "#EXTINF:6.0,",
        "<seg-00001.m4s>",
    ]


def test_rewrites_alternate_renditions_and_keys():
    playlist = "\n".join(
        [
            '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",NAME="English",URI="audio/index.m3u8"',
            '#EXT-X-KEY:METHOD=AES-128,URI="keys/1.bin",IV=0x00',
            '#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=100000,URI="iframe.m3u8"',
        ]
    )

    rewritten = rewrite(playlist, mark)

    assert 'URI="<audio/index.m3u8>"' in rewritten
    assert 'URI="<keys/1.bin>"' in rewritten
    assert 'URI="<iframe.m3u8>"' in rewritten
    # Other attributes on the same line are untouched.
    assert 'GROUP-ID="a"' in rewritten
    assert "IV=0x00" in rewritten


def test_leaves_absolute_urls_alone():
    """
    Either it is not ours to sign, or it has been rewritten once already.
    Signing a second time corrupts it.
    """
    playlist = "\n".join(
        [
            "https://cdn.example/seg-1.ts",
            "//cdn.example/seg-2.ts",
            '#EXT-X-MAP:URI="https://cdn.example/init.mp4"',
        ]
    )

    assert rewrite(playlist, mark) == playlist


def test_preserves_blank_lines_comments_and_trailing_newline():
    playlist = "#EXTM3U\n\n# a plain comment\nseg.ts\n"

    assert rewrite(playlist, mark) == "#EXTM3U\n\n# a plain comment\n<seg.ts>\n"


def test_normalises_windows_line_endings():
    # A transcoder run on a different platform should not change the output.
    assert rewrite("#EXTM3U\r\nseg.ts\r\n", mark) == "#EXTM3U\n<seg.ts>\n"


def test_empty_uri_attribute_is_left_alone():
    # Malformed, but resolving "" would produce a signed URL for the bucket
    # root, which is worse than passing the malformed line through.
    assert rewrite('#EXT-X-MAP:URI=""', mark) == '#EXT-X-MAP:URI=""'


class TestTellingPlaylistsFromSegments:
    """
    The two need opposite treatment: a segment gets a presigned bucket URL, a
    playlist gets routed back through the rewriting endpoint so its own URIs are
    resolved when it is fetched rather than signed now and stale by then.
    """

    def test_recognises_playlists(self):
        for uri in ("index.m3u8", "audio/index.M3U8", "v0/index.m3u"):
            assert is_playlist(uri), uri

    def test_recognises_segments(self):
        for uri in ("seg-00001.ts", "init.mp4", "seg.m4s", "keys/1.bin"):
            assert not is_playlist(uri), uri

    def test_ignores_a_query_string(self):
        # A rewritten URI can carry one, and it is still a playlist.
        assert is_playlist("index.m3u8?token=abc")
        assert not is_playlist("seg.ts?token=abc")


class TestPathSafety:
    """
    The path from the URL is concatenated into an object key, and the bucket is
    private so that access is decided by this service rather than by whoever
    holds a URL. If a path can climb out of its prefix, the private bucket has
    bought nothing.
    """

    def test_accepts_ordinary_playlist_paths(self):
        for path in ("master.m3u8", "720p/index.m3u8", "audio/en/index.m3u8"):
            assert is_safe_path(path), path

    def test_refuses_climbing_out_of_the_prefix(self):
        for path in (
            "../other/master.m3u8",
            "720p/../../other/master.m3u8",
            "..",
            "../",
        ):
            assert not is_safe_path(path), path

    def test_refuses_absolute_paths(self):
        assert not is_safe_path("/etc/passwd")

    def test_refuses_backslashes(self):
        # Not a separator here, but it is elsewhere, and a key is not worth
        # being clever about.
        assert not is_safe_path("720p\\..\\..\\other.m3u8")

    def test_refuses_empty(self):
        assert not is_safe_path("")

    def test_allows_dots_that_are_not_traversal(self):
        # A rendition directory may legitimately contain a dot, and refusing
        # every dot would reject valid keys.
        assert is_safe_path("v1.5/index.m3u8")
        assert is_safe_path("seg..name/index.m3u8")
