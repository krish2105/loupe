import base64
import hashlib

from app import bunny


class TestUploadSignature:
    def test_matches_the_documented_construction(self):
        """
        Bunny specifies sha256(library + key + expiry + video) as hex. Computed
        here independently rather than by calling the same helper twice.
        """
        expected = hashlib.sha256(b"12345secret-key1700000000abc-guid").hexdigest()

        assert (
            bunny.upload_signature("12345", "secret-key", "abc-guid", 1700000000)
            == expected
        )

    def test_changing_any_input_changes_the_signature(self):
        base = bunny.upload_signature("12345", "key", "guid", 1700000000)

        assert bunny.upload_signature("99999", "key", "guid", 1700000000) != base
        assert bunny.upload_signature("12345", "other", "guid", 1700000000) != base
        assert bunny.upload_signature("12345", "key", "other", 1700000000) != base
        assert bunny.upload_signature("12345", "key", "guid", 1700000001) != base


class TestSignedPlaybackUrl:
    def test_token_is_urlsafe_base64_of_the_raw_digest(self):
        """
        The failure mode this guards: a signature that is right as bytes but
        wrong as text yields a 403 from a CDN edge with no diagnostic at all.
        The expectation is built with urlsafe_b64encode, which is a genuinely
        different route to the same answer.
        """
        digest = hashlib.sha256(b"tk/abc/playlist.m3u81700000000").digest()
        expected_token = base64.urlsafe_b64encode(digest).decode().rstrip("=")

        url = bunny.signed_playback_url(
            "loupe.b-cdn.net", "/abc/playlist.m3u8", "tk", 1700000000
        )

        assert f"token={expected_token}" in url
        assert "expires=1700000000" in url
        assert url.startswith("https://loupe.b-cdn.net/abc/playlist.m3u8?")

    def test_token_carries_no_characters_that_break_a_query_string(self):
        url = bunny.signed_playback_url(
            "zone.b-cdn.net", "/v/playlist.m3u8", "key", 1900000000
        )
        token = url.split("token=")[1].split("&")[0]

        assert "+" not in token
        assert "/" not in token
        assert "=" not in token

    def test_a_path_without_a_leading_slash_is_normalised(self):
        with_slash = bunny.signed_playback_url("z.net", "/a/b.m3u8", "k", 100)
        without_slash = bunny.signed_playback_url("z.net", "a/b.m3u8", "k", 100)

        # Otherwise the token signs a different string than the path requested,
        # and playback fails only for whichever caller forgot the slash.
        assert with_slash == without_slash

    def test_expiry_is_part_of_what_is_signed(self):
        first = bunny.signed_playback_url("z.net", "/a.m3u8", "k", 100)
        second = bunny.signed_playback_url("z.net", "/a.m3u8", "k", 200)

        assert first.split("token=")[1] != second.split("token=")[1]


class TestStatusMapping:
    def test_encoding_states_map_onto_the_stage_machine(self):
        assert bunny.STATUS_TO_STAGE[bunny.BunnyStatus.QUEUED] == "transcoding"
        assert bunny.STATUS_TO_STAGE[bunny.BunnyStatus.ENCODING] == "transcoding"
        assert bunny.STATUS_TO_STAGE[bunny.BunnyStatus.FINISHED] == "transcoded"
        assert bunny.STATUS_TO_STAGE[bunny.BunnyStatus.FAILED] == "failed_transcoding"

    def test_events_that_are_not_stage_transitions_are_absent(self):
        # A resolution finishing is progress within encoding, and captions
        # being generated is not our pipeline at all. Mapping either would
        # move the stage machine backwards or sideways.
        assert bunny.BunnyStatus.RESOLUTION_FINISHED not in bunny.STATUS_TO_STAGE
        assert bunny.BunnyStatus.CAPTIONS_GENERATED not in bunny.STATUS_TO_STAGE

    def test_every_mapped_stage_exists_in_the_schema_enum(self):
        # These strings are cast to processing_status in SQL; a typo would only
        # surface as a runtime cast error inside a webhook.
        valid = {
            "uploaded",
            "transcoding",
            "failed_transcoding",
            "transcoded",
            "transcribing",
            "failed_transcribing",
            "transcribed",
            "chunking",
            "failed_chunking",
            "embedding",
            "failed_embedding",
            "indexed",
            "enriched",
            "referenced_only",
        }
        assert set(bunny.STATUS_TO_STAGE.values()) <= valid
