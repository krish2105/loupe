from datetime import UTC, datetime

from app.personas import PERSONAS, Candidate, affinity, generate_history, split_holdout

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def catalogue(count: int = 40) -> list[Candidate]:
    channels = ["mlsys", "stanford-mlsys", "neurips", "pytorch-conf"]
    words = ["memory bandwidth", "scaling laws", "quantisation", "roofline kernel"]
    return [
        Candidate(
            video_id=f"v{index:03d}",
            channel_handle=channels[index % len(channels)],
            title=f"Talk {index} on {words[index % len(words)]}",
            view_count=1000 + (index * 137) % 90000,
        )
        for index in range(count)
    ]


class TestPersonaDefinitions:
    def test_every_event_is_labelled_synthetic(self):
        """
        §12.2: "Never present synthetic results as real user data."

        The label is a column, not prose, so the distinction survives into
        every query anyone writes later.
        """
        events = generate_history(PERSONAS[0], catalogue(), "u1", NOW)
        assert events
        assert all(event["is_synthetic"] is True for event in events)

    def test_the_dataset_includes_someone_the_model_should_lose_on(self):
        """
        The 'skimmer' watches by popularity alone. Without them the comparison
        against a popularity baseline is rigged in the model's favour, and a
        win would mean nothing at all.
        """
        skimmer = next(p for p in PERSONAS if p.key == "skimmer")
        assert skimmer.popularity_bias >= 0.7
        assert not skimmer.favourite_channels

    def test_personas_differ_from_each_other(self):
        keys = {p.key for p in PERSONAS}
        assert len(keys) == len(PERSONAS)
        # If every persona liked the same channels there would be no
        # personalisation signal to learn.
        assert len({p.favourite_channels for p in PERSONAS}) > 1


class TestGeneration:
    def test_it_is_deterministic(self):
        first = generate_history(PERSONAS[0], catalogue(), "u1", NOW)
        second = generate_history(PERSONAS[0], catalogue(), "u1", NOW)
        assert first == second

    def test_different_users_get_different_histories(self):
        first = generate_history(PERSONAS[0], catalogue(), "u1", NOW)
        second = generate_history(PERSONAS[0], catalogue(), "u2", NOW)
        assert first != second

    def test_events_are_ordered_in_time(self):
        events = generate_history(PERSONAS[1], catalogue(), "u1", NOW)
        times = [event["occurred_at"] for event in events]
        assert times == sorted(times)

    def test_watch_percentage_stays_in_range(self):
        for persona in PERSONAS:
            for event in generate_history(persona, catalogue(), "u1", NOW):
                assert 0.0 <= event["watch_pct"] <= 1.0

    def test_preferences_actually_bias_the_result(self):
        """
        If the generator produced uniform picks there would be nothing to
        learn, and a model beating popularity would be luck.
        """
        deep = next(p for p in PERSONAS if p.key == "deep-diver")
        events = generate_history(deep, catalogue(200), "u1", NOW)

        items = {event["video_id"] for event in events}
        favoured = {
            candidate.video_id
            for candidate in catalogue(200)
            if candidate.channel_handle in deep.favourite_channels
        }
        overlap = len(items & favoured) / max(1, len(items))

        # A quarter of the catalogue is their channel; they should exceed that.
        assert overlap > 0.35

    def test_an_empty_catalogue_produces_nothing(self):
        assert generate_history(PERSONAS[0], [], "u1", NOW) == []

    def test_affinity_rewards_both_channel_and_topic(self):
        persona = next(p for p in PERSONAS if p.key == "systems-engineer")

        both = Candidate("v", "mlsys", "memory bandwidth in serving", 1)
        channel_only = Candidate("v", "mlsys", "unrelated subject", 1)
        neither = Candidate("v", "icml", "unrelated subject", 1)

        assert affinity(persona, both) > affinity(persona, channel_only)
        assert affinity(persona, channel_only) > affinity(persona, neither)


class TestHoldout:
    def test_it_splits_by_time_not_at_random(self):
        """
        A random split leaks the future into training — the model sees what the
        user watched *after* the items it is asked to predict. It is the single
        most common way an offline recommender result becomes meaningless.
        """
        events = generate_history(PERSONAS[0], catalogue(), "u1", NOW)
        train, held = split_holdout(events)

        latest_train = max(event["occurred_at"] for event in train)
        held_events = [e for e in events if e["video_id"] in held]
        if held_events:
            assert min(e["occurred_at"] for e in held_events) >= latest_train

    def test_items_seen_in_training_are_not_prediction_targets(self):
        events = generate_history(PERSONAS[2], catalogue(), "u1", NOW)
        train, held = split_holdout(events)

        trained_on = {event["video_id"] for event in train}
        # Otherwise the metric rewards memorisation rather than prediction.
        assert not (held & trained_on)

    def test_roughly_a_fifth_is_held_back(self):
        events = generate_history(PERSONAS[0], catalogue(), "u1", NOW)
        train, _ = split_holdout(events, 0.2)
        assert 0.7 <= len(train) / len(events) <= 0.9

    def test_empty_history(self):
        assert split_holdout([]) == ([], set())
