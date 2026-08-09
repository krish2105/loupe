from app.playback import playable_url

"""
Rendering a stored asset reference as a playable URL.

The column holds either an absolute URL (the seeded reference stream) or a
bucket key produced by our own transcoder. The watch page feeds whatever comes
back straight to the player, so a key returned raw is a relative path that
resolves against the web app's origin and 404s there — which looks like a
missing video rather than a missing base URL.
"""

MEDIA = "https://loupe-media.onrender.com"


class TestAbsoluteReferences:
    def test_passes_an_https_url_through_untouched(self):
        stream = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

        assert playable_url(stream, MEDIA) == stream

    def test_passes_a_protocol_relative_url_through(self):
        assert playable_url("//cdn.example/a.m3u8", MEDIA) == "//cdn.example/a.m3u8"

    def test_does_not_route_an_absolute_url_through_the_media_service(self):
        # Doing so would proxy a stream we do not host and cannot sign.
        assert MEDIA not in playable_url("https://cdn.example/a.m3u8", MEDIA)


class TestBucketKeys:
    def test_rewrites_a_key_into_the_media_service_route(self):
        """
        The stored key and the route are different shapes. The key is
        `videos/<id>/hls/<tail>`; the route is `/v1/hls/<id>/<tail>` and
        rebuilds the key itself. Prefixing the whole key made the route read
        id="videos" and look for `videos/videos/<id>/...`, which 404s and looks
        like missing media rather than a malformed URL.
        """
        assert playable_url("videos/abc/hls/master.m3u8", MEDIA) == (
            f"{MEDIA}/v1/hls/abc/master.m3u8"
        )

    def test_keeps_a_nested_rendition_path(self):
        assert playable_url("videos/abc/hls/720p/index.m3u8", MEDIA) == (
            f"{MEDIA}/v1/hls/abc/720p/index.m3u8"
        )

    def test_tolerates_a_trailing_slash_on_the_base(self):
        assert playable_url("videos/abc/hls/master.m3u8", MEDIA + "/") == (
            f"{MEDIA}/v1/hls/abc/master.m3u8"
        )

    def test_tolerates_a_leading_slash_on_the_key(self):
        assert playable_url("/videos/abc/hls/master.m3u8", MEDIA) == (
            f"{MEDIA}/v1/hls/abc/master.m3u8"
        )

    def test_refuses_to_guess_at_an_unrecognised_layout(self):
        # Better None than a URL built on an assumption about a key shape that
        # has since changed.
        assert playable_url("some/other/layout.m3u8", MEDIA) is None


class TestNothingToPlay:
    def test_returns_none_for_an_empty_column(self):
        assert playable_url(None, MEDIA) is None
        assert playable_url("", MEDIA) is None
        assert playable_url("   ", MEDIA) is None

    def test_returns_none_for_a_key_with_no_media_service(self):
        """
        A key alone cannot be opened by anything. Returning it raw would hand
        the player a relative path that fails somewhere less obvious than here.
        """
        assert playable_url("videos/abc/hls/master.m3u8", "") is None

    def test_still_returns_an_absolute_url_with_no_media_service(self):
        # It does not need one.
        stream = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

        assert playable_url(stream, "") == stream
