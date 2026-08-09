from datetime import UTC, datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from app.s3 import hls_key, presigned_url

"""
S3 presigning.

Every signature here is pinned to a fixed instant, because the point of writing
SigV4 out by hand rather than importing boto3 is that it can be checked. A
signature is a pure function of its inputs; if the timestamp moves, nothing can
be asserted about the output beyond "it is 64 hex characters".

The signatures themselves were produced by this implementation and verified
against Backblaze B2 with a live request. They are regression anchors: if a
change alters one, the change altered the signature, and the next thing that
happens is an opaque 403 from an edge in production.
"""

FIXED = datetime(2026, 8, 9, 15, 22, 0, tzinfo=UTC)

COMMON = {
    "endpoint": "https://s3.us-east-005.backblazeb2.com",
    "region": "us-east-005",
    "bucket": "loupe-media",
    "access_key": "005e3159f22f3640000000001",
    "secret_key": "K005TESTTESTTESTTESTTESTTESTTES",
    "expires_in": 3600,
    "now": FIXED,
}


def sign(**overrides) -> str:
    return presigned_url(**{**COMMON, **overrides})


class TestShape:
    def test_uses_path_style_addressing(self):
        """
        B2's endpoint accepts path style, and the bucket name therefore belongs
        in the path rather than the host. Virtual-hosted style would sign a
        different canonical URI and fail verification.
        """
        parts = urlsplit(sign(key="videos/abc/hls/master.m3u8"))

        assert parts.netloc == "s3.us-east-005.backblazeb2.com"
        assert parts.path == "/loupe-media/videos/abc/hls/master.m3u8"

    def test_carries_the_six_required_parameters(self):
        query = parse_qs(urlsplit(sign(key="a.ts")).query)

        assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
        assert query["X-Amz-Credential"] == [
            "005e3159f22f3640000000001/20260809/us-east-005/s3/aws4_request"
        ]
        assert query["X-Amz-Date"] == ["20260809T152200Z"]
        assert query["X-Amz-Expires"] == ["3600"]
        assert query["X-Amz-SignedHeaders"] == ["host"]
        assert len(query["X-Amz-Signature"][0]) == 64


class TestDeterminism:
    def test_same_inputs_produce_the_same_signature(self):
        assert sign(key="a.ts") == sign(key="a.ts")

    def test_signature_is_stable_across_versions(self):
        # A regression anchor. If this changes, the signing changed, and the
        # symptom in production is a 403 with no explanation.
        signature = parse_qs(urlsplit(sign(key="videos/abc/hls/master.m3u8")).query)[
            "X-Amz-Signature"
        ][0]
        assert signature == (
            "4a5d69e83790617a45f10f215b42b4b1cb7561604d832ba9eb9ed21ba3354956"
        )

    def test_a_different_key_changes_the_signature(self):
        assert sign(key="a.ts") != sign(key="b.ts")

    def test_a_different_second_changes_the_signature(self):
        later = FIXED.replace(second=1)
        assert sign(key="a.ts") != sign(key="a.ts", now=later)


class TestKeyEncoding:
    def test_slashes_stay_literal(self):
        # They separate path segments. Encoding them signs a different resource.
        assert "/loupe-media/videos/abc/hls/master.m3u8" in sign(
            key="videos/abc/hls/master.m3u8"
        )

    def test_spaces_and_reserved_characters_are_encoded(self):
        """
        The most common cause of a signature that works on simple keys and 403s
        on real ones. Titles and rendition names both produce these eventually.
        """
        path = urlsplit(sign(key="videos/a b+c&d.ts")).path

        assert path == "/loupe-media/videos/a%20b%2Bc%26d.ts"

    def test_a_leading_slash_on_the_key_is_not_doubled(self):
        assert urlsplit(sign(key="/videos/a.ts")).path == "/loupe-media/videos/a.ts"


class TestTimezoneSafety:
    def test_naive_datetimes_are_refused(self):
        """
        A naive datetime would be signed as if it were UTC, so a machine set to
        UTC+5:30 would mint URLs that expired five hours ago. That presents as a
        clock problem on the server, which it is not, and it is silent until
        something 403s.
        """
        with pytest.raises(ValueError, match="timezone-aware"):
            sign(key="a.ts", now=datetime(2026, 8, 9, 15, 22, 0))

    def test_a_non_utc_timezone_is_converted_rather_than_rejected(self):
        from datetime import timedelta

        kolkata = FIXED.astimezone(timezone(timedelta(hours=5, minutes=30)))

        # Same instant, different wall clock — must sign identically.
        assert sign(key="a.ts", now=kolkata) == sign(key="a.ts")


class TestKeyLayout:
    def test_groups_every_rendition_under_one_prefix(self):
        """
        One prefix per video, so a takedown is a prefix delete rather than a
        hunt for every rendition. That matters now that anyone can upload and
        the platform owes a removal that actually removes.
        """
        assert hls_key("abc") == "videos/abc/hls"
        assert hls_key("abc", "master.m3u8") == "videos/abc/hls/master.m3u8"
        assert hls_key("abc", "720p", "seg-1.ts") == "videos/abc/hls/720p/seg-1.ts"

    def test_tolerates_slashes_around_the_parts(self):
        assert hls_key("abc", "/720p/", "/seg-1.ts") == "videos/abc/hls/720p/seg-1.ts"
