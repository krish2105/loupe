from app.playlists import (
    INCLUSION_FLOOR,
    MIN_ITEMS,
    VideoCard,
    compose,
    write_rationale,
)
from app.retrieval import RetrievedChunk

"""
AI playlist composition (§11).

Pure over plain data, so the contract — fewer items rather than poor ones,
ordering explained rather than asserted — is tested without a model, a
database, or an embedding.
"""


def chunk(video_id: str, similarity: float, start_sec: float = 60.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"c-{video_id}",
        video_id=video_id,
        chunk_index=0,
        start_sec=start_sec,
        end_sec=start_sec + 45,
        text_display="The thing about attention is that it scales with sequence length squared.",
        text_normalised="the thing about attention",
        similarity=similarity,
    )


def card(video_id: str, channel: str, title: str | None = None) -> VideoCard:
    return VideoCard(
        video_id=video_id,
        title=title or f"Talk {video_id}",
        channel_id=channel,
        channel_name=f"Channel {channel}",
    )


def catalogue(*pairs: tuple[str, str]) -> dict[str, VideoCard]:
    return {video_id: card(video_id, channel) for video_id, channel in pairs}


class TestTheFailureClause:
    def test_it_returns_fewer_items_rather_than_padding(self):
        """
        §11: "Return fewer items rather than padding with poor matches."

        Four talks are related; two are not. The playlist is four long.
        """
        chunks = [
            chunk("a", 0.71),
            chunk("b", 0.62),
            chunk("c", 0.55),
            chunk("d", 0.46),
            chunk("e", 0.12),
            chunk("f", 0.04),
        ]
        cards = catalogue(
            ("a", "1"), ("b", "2"), ("c", "3"), ("d", "4"), ("e", "5"), ("f", "6")
        )

        proposal = compose("attention scaling", chunks, cards, limit=8)

        assert [item.video_id for item in proposal.items] == ["a", "b", "c", "d"]

    def test_it_refuses_rather_than_making_a_two_item_playlist(self):
        """
        A list of two is a search result. Refusing says so instead of dressing
        it up, which is the same judgement ask-video makes on weak retrieval.
        """
        chunks = [chunk("a", 0.80), chunk("b", 0.70), chunk("c", 0.05)]
        cards = catalogue(("a", "1"), ("b", "2"), ("c", "3"))

        proposal = compose("something barely covered", chunks, cards)

        assert proposal.refused
        assert proposal.items == ()
        assert proposal.reason
        # A refusal carries no rationale, because there is no ordering to explain.
        assert proposal.rationale == ""

    def test_nothing_below_the_floor_ever_appears(self):
        chunks = [chunk(str(i), 0.95 - i * 0.06) for i in range(9)]
        cards = catalogue(*((str(i), str(i)) for i in range(9)))

        proposal = compose("anything", chunks, cards, limit=12)

        assert all(item.score >= INCLUSION_FLOOR for item in proposal.items)

    def test_an_off_topic_brief_refuses(self):
        """
        The measurement this floor exists for. Composing "underwater basket
        weaving for beginners" against a corpus of systems talks scored
        0.363–0.372 across every video — comfortably above the citation
        threshold this constant was originally borrowed from, which produced a
        full eight-talk playlist of MLSys talks.

        bge-m3 puts unrelated text around 0.35, so a threshold down there sits
        inside the model's noise floor and separates nothing.
        """
        chunks = [chunk(str(i), 0.372 - i * 0.002) for i in range(8)]
        cards = catalogue(*((str(i), str(i % 3)) for i in range(8)))

        proposal = compose("underwater basket weaving for beginners", chunks, cards)

        assert proposal.refused

    def test_a_video_missing_from_the_catalogue_is_dropped_not_crashed(self):
        """
        Retrieval and the metadata read are two queries. A video deleted between
        them is rare and entirely possible.
        """
        chunks = [chunk("a", 0.8), chunk("gone", 0.7), chunk("b", 0.6), chunk("c", 0.5)]
        cards = catalogue(("a", "1"), ("b", "2"), ("c", "3"))

        proposal = compose("brief", chunks, cards)

        assert [item.video_id for item in proposal.items] == ["a", "b", "c"]


class TestOrdering:
    def test_the_strongest_match_leads(self):
        chunks = [chunk("a", 0.9), chunk("b", 0.8), chunk("c", 0.7)]
        proposal = compose(
            "brief", chunks, catalogue(("a", "1"), ("b", "2"), ("c", "3"))
        )

        assert proposal.items[0].video_id == "a"

    def test_one_talk_per_channel_before_any_channel_repeats(self):
        """
        Six strong talks, four of them from one conference. Without the spread
        the playlist is that conference's programme rather than an answer to
        the brief.
        """
        chunks = [
            chunk("a1", 0.90),
            chunk("a2", 0.88),
            chunk("a3", 0.86),
            chunk("a4", 0.84),
            chunk("b1", 0.60),
            chunk("c1", 0.55),
        ]
        cards = catalogue(
            ("a1", "A"), ("a2", "A"), ("a3", "A"), ("a4", "A"),
            ("b1", "B"), ("c1", "C"),
        )

        order = [item.video_id for item in compose("brief", chunks, cards).items]

        assert order[:3] == ["a1", "b1", "c1"]
        assert order[3:] == ["a2", "a3", "a4"]

    def test_a_channels_second_talk_never_outranks_anothers_first(self):
        chunks = [chunk("a1", 0.90), chunk("a2", 0.85), chunk("b1", 0.50)]
        cards = catalogue(("a1", "A"), ("a2", "A"), ("b1", "B"))

        order = [item.video_id for item in compose("brief", chunks, cards).items]

        # a2 scores higher than b1 and still comes after it.
        assert order == ["a1", "b1", "a2"]

    def test_the_limit_is_respected(self):
        chunks = [chunk(str(i), 0.9) for i in range(20)]
        cards = catalogue(*((str(i), str(i)) for i in range(20)))

        assert len(compose("brief", chunks, cards, limit=5).items) == 5

    def test_a_limit_below_the_minimum_is_raised_to_it(self):
        chunks = [chunk(str(i), 0.9) for i in range(6)]
        cards = catalogue(*((str(i), str(i)) for i in range(6)))

        assert len(compose("brief", chunks, cards, limit=1).items) == MIN_ITEMS


class TestRationale:
    def test_every_number_in_it_is_read_off_the_result(self):
        chunks = [chunk("a", 0.81), chunk("b", 0.62), chunk("c", 0.47)]
        cards = catalogue(("a", "1"), ("b", "2"), ("c", "3"))

        proposal = compose("scaling laws", chunks, cards)

        assert "3 talks" in proposal.rationale
        assert "3 channels" in proposal.rationale
        assert "0.81" in proposal.rationale
        assert "0.47" in proposal.rationale
        assert "scaling laws" in proposal.rationale

    def test_it_states_the_ordering_rule_it_actually_used(self):
        chunks = [chunk("a", 0.8), chunk("b", 0.7), chunk("c", 0.6)]
        rationale = compose(
            "brief", chunks, catalogue(("a", "1"), ("b", "2"), ("c", "3"))
        ).rationale

        assert "strongest" in rationale
        assert "each channel" in rationale

    def test_one_channel_is_not_described_as_channels(self):
        items = compose(
            "brief",
            [chunk("a", 0.8), chunk("b", 0.7), chunk("c", 0.6)],
            catalogue(("a", "A"), ("b", "A"), ("c", "A")),
        ).items

        assert "1 channel," in write_rationale("brief", items)


class TestTitle:
    def test_it_reads_as_a_title_not_a_query(self):
        chunks = [chunk("a", 0.8), chunk("b", 0.7), chunk("c", 0.6)]
        cards = catalogue(("a", "1"), ("b", "2"), ("c", "3"))

        proposal = compose(
            "how do transformers handle long context?", chunks, cards
        )

        assert proposal.title == "How do transformers handle long context"

    def test_a_refusal_still_carries_one(self):
        """The UI shows what was asked for, so the title survives the refusal."""
        proposal = compose("obscure brief", [], {})

        assert proposal.refused
        assert proposal.title == "Obscure brief"
