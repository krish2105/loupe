from app.chapters import build_chapters, cosine_similarity, find_boundaries
from app.embed import HashingEmbedder


class TestCosine:
    def test_identical_vectors(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

    def test_a_zero_vector_is_similar_to_nothing(self):
        # Rather than a division by zero, which is how this normally surfaces.
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_mismatched_lengths_do_not_crash(self):
        assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0


class TestBoundaryDetection:
    """
    §10.2 stage one: cosine drift between consecutive windows finds boundaries.

    Measured, not asked for. The whole reason the plan splits detection from
    naming is that a model asked for "the chapters" returns plausible ones with
    no way to tell a good answer from a confident one.
    """

    def test_it_finds_a_real_topic_change(self):
        embedder = HashingEmbedder()
        first_topic = [
            "memory bandwidth roofline arithmetic intensity bound",
            "bandwidth bound kernels memory roofline",
            "roofline plot memory bandwidth again",
            "memory bound bandwidth roofline",
        ]
        second_topic = [
            "continuous batching admission queue tail latency",
            "batching queue latency admission control",
            "tail latency batching queue depth",
            "admission batching latency queue",
        ]
        texts = first_topic + second_topic
        embeddings = embedder.embed(texts)
        starts = [float(i * 120) for i in range(len(texts))]

        boundaries = find_boundaries(embeddings, starts)

        assert boundaries, "no boundary found at an obvious topic change"
        # The change is between index 3 and 4.
        assert any(abs(b.chunk_index - 4) <= 1 for b in boundaries)

    def test_uniform_content_yields_no_chapters(self):
        embedder = HashingEmbedder()
        texts = ["memory bandwidth roofline bound"] * 10
        embeddings = embedder.embed(texts)
        starts = [float(i * 120) for i in range(10)]

        # §11's failure mode is an unsegmented scrubber. A talk that never
        # changes subject should produce nothing rather than arbitrary cuts.
        assert find_boundaries(embeddings, starts) == []

    def test_too_few_chunks_yields_nothing(self):
        assert find_boundaries([[1.0, 0.0]] * 3, [0.0, 1.0, 2.0]) == []

    def test_boundaries_are_not_crowded_together(self):
        embedder = HashingEmbedder()
        texts = [
            "alpha alpha alpha",
            "alpha alpha alpha",
            "beta beta beta",
            "gamma gamma gamma",
            "delta delta delta",
            "epsilon epsilon epsilon",
            "zeta zeta zeta",
            "eta eta eta",
        ]
        embeddings = embedder.embed(texts)
        # Every chunk is 10 seconds apart — below MIN_CHAPTER_SECONDS.
        starts = [float(i * 10) for i in range(len(texts))]

        boundaries = find_boundaries(embeddings, starts)

        # Two chapters starting ten seconds apart is worse than one.
        assert len(boundaries) <= 1


class TestChapterAssembly:
    def test_the_first_chapter_starts_at_zero(self):
        from app.chapters import Boundary

        chapters = build_chapters(
            [Boundary(4, 300.0, 0.4), Boundary(8, 700.0, 0.3)],
            total_duration=1000.0,
            titles=["Opening", "Middle", "End"],
        )

        # A talk does not begin at its first topic shift.
        assert chapters[0].start_sec == 0.0
        assert [c.title for c in chapters] == ["Opening", "Middle", "End"]
        assert chapters[-1].end_sec == 1000.0

    def test_chapters_are_contiguous_and_forward(self):
        from app.chapters import Boundary

        chapters = build_chapters(
            [Boundary(4, 300.0, 0.4), Boundary(8, 700.0, 0.3)], 1000.0, []
        )

        for earlier, later in zip(chapters, chapters[1:], strict=False):
            assert earlier.end_sec == later.start_sec
            assert earlier.end_sec > earlier.start_sec

    def test_confidence_is_bounded(self):
        from app.chapters import Boundary

        chapters = build_chapters([Boundary(4, 300.0, 99.0)], 1000.0, [])

        # Drift is a distance, not a probability; reporting it raw would
        # overstate it.
        assert all(0.0 <= c.confidence <= 1.0 for c in chapters)

    def test_no_boundaries_means_no_chapters(self):
        assert build_chapters([], 1000.0, []) == []


class TestHashingEmbedder:
    def test_vectors_are_normalised(self):
        [vector] = HashingEmbedder().embed(["memory bandwidth"])
        magnitude = sum(value * value for value in vector) ** 0.5
        assert abs(magnitude - 1.0) < 1e-9

    def test_related_texts_are_closer_than_unrelated_ones(self):
        embedder = HashingEmbedder()
        a, b, c = embedder.embed(
            [
                "memory bandwidth roofline",
                "memory bandwidth bound kernels",
                "continuous batching admission queue",
            ]
        )
        assert cosine_similarity(a, b) > cosine_similarity(a, c)

    def test_it_is_deterministic(self):
        assert HashingEmbedder().embed(["x y z"]) == HashingEmbedder().embed(["x y z"])

    def test_dimension_matches_the_schema(self):
        # transcript_chunks.embedding is vector(1024); a mismatch fails at
        # insert time with an opaque error.
        [vector] = HashingEmbedder().embed(["anything"])
        assert len(vector) == 1024
