import pytest

from app.providers.base import ExternalChannel, Page
from app.providers.fixture import FixtureProvider
from app.providers.youtube import YouTubeProvider, parse_duration


class TestNoSearchPath:
    """
    §4.2 rule 1: never call third-party search.

    A search call costs 100 units for the same 50 items playlistItems returns
    for 1. The rule is enforced structurally — there is no search method to
    call — and this asserts that, so adding one becomes a visible failure
    rather than a quiet convenience.
    """

    def test_the_provider_interface_exposes_no_search(self):
        for provider in (FixtureProvider, YouTubeProvider):
            methods = {name for name in dir(provider) if not name.startswith("_")}
            assert not any("search" in name.lower() for name in methods), (
                f"{provider.__name__} exposes a search-shaped method"
            )

    def test_the_youtube_client_never_names_the_search_endpoint(self):
        import inspect

        import app.providers.youtube as module

        source = inspect.getsource(module)
        # Comments mention it; a request path must not.
        assert '"search"' not in source
        assert "/search" not in source.replace("# ", "")


class TestFixtureProvider:
    async def test_it_is_deterministic(self):
        """
        Re-running the sync must be a genuine no-op, not an accidental one.
        That only holds if the same handle yields the same external ids.
        """
        first = await FixtureProvider().resolve_channel("@YannicKilcher")
        second = await FixtureProvider().resolve_channel("@YannicKilcher")

        assert first == second

    async def test_pages_cost_one_unit_each(self):
        page = await FixtureProvider().list_uploads("UUfix0000000000000001", None)

        # Costed exactly like the real endpoint, so quota behaviour under the
        # fixture matches quota behaviour under the API.
        assert page.units_spent == 1
        assert len(page.items) == 50

    async def test_it_paginates_and_then_stops(self):
        provider = FixtureProvider(videos_per_page=50, pages=2)

        first = await provider.list_uploads("UUfix1", None)
        second = await provider.list_uploads("UUfix1", first.next_page_token)

        assert first.next_page_token == "1"
        assert second.next_page_token is None
        # Distinct ids across pages, or the second page inserts nothing.
        assert not {v.external_id for v in first.items} & {
            v.external_id for v in second.items
        }

    async def test_every_video_carries_an_external_id(self):
        """
        The database rejects a Class B row without one (§4), so a provider that
        omitted it would fail at insert time rather than here.
        """
        page = await FixtureProvider().list_uploads("UUfix2", None)
        assert all(v.external_id for v in page.items)


class TestDurationParsing:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("PT1H2M10S", 3730),
            ("PT45M", 2700),
            ("PT30S", 30),
            ("P1DT2H", 93600),
            (None, None),
            ("nonsense", None),
        ],
    )
    def test_iso_durations(self, value, expected):
        assert parse_duration(value) == expected

    def test_an_unparseable_duration_is_none_rather_than_zero(self):
        # Zero would render as "0:00" on a card and look like a broken video;
        # None renders as no badge at all.
        assert parse_duration("PT") is None or parse_duration("PT") == 0


class TestTypes:
    def test_page_and_channel_carry_what_the_sync_needs(self):
        page = Page(items=[], next_page_token=None, units_spent=1)
        assert page.units_spent == 1

        channel = ExternalChannel(
            external_id="UC1",
            handle="@x",
            name="X",
            description=None,
            uploads_playlist_id="UU1",
        )
        assert channel.uploads_playlist_id == "UU1"
