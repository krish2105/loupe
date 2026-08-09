-- 0005 — recommendation features
-- Plan refs: §6.4, §12 (two-stage design)
--
-- All three tables are nightly precomputes. §5 gives the ranker a sub-100ms budget
-- and says it reads precomputed features, so nothing here is calculated on request.

CREATE TABLE user_topic_affinity (
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  topic       text NOT NULL,
  score       real NOT NULL CHECK (score >= 0 AND score <= 1),
  computed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, topic)
);

CREATE INDEX user_topic_affinity_top_idx
  ON user_topic_affinity (user_id, score DESC);

-- §12.1 stage 1: content-similarity neighbours of recently watched videos.
-- Top-K per video from content embeddings.
CREATE TABLE video_similarity (
  video_id    uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  neighbour_id uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  rank        integer NOT NULL CHECK (rank >= 0),
  similarity  real NOT NULL CHECK (similarity >= -1 AND similarity <= 1),
  computed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (video_id, neighbour_id),
  CONSTRAINT video_similarity_not_self CHECK (video_id <> neighbour_id)
);

CREATE INDEX video_similarity_rank_idx ON video_similarity (video_id, rank);

-- §6.4: materialised per user, refreshed nightly. §12.1 targets ~500 candidates.
CREATE TABLE feed_candidates (
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id    uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  rank        integer NOT NULL CHECK (rank >= 0),
  score       real NOT NULL,
  -- §11 personalised feed contract: ranked list with reason codes. The reason is
  -- part of the output, so it is stored with the candidate.
  reason_code text NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, video_id)
);

CREATE INDEX feed_candidates_rank_idx ON feed_candidates (user_id, rank);
