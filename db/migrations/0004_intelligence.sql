-- 0004 — the intelligence layer
-- Plan refs: §6.3, §10.2 (stage specifications), §11 (AI feature contracts)
--
-- Every table here is Class A only. §4 states the capability asymmetry plainly:
-- referenced content carries no transcript, and closing that gap by unofficial
-- means is both a licensing risk and worse engineering. The assert_owned_video
-- trigger makes that a property of the database, not a habit.

CREATE TABLE transcripts (
  video_id       uuid PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
  language       text NOT NULL,
  engine         text NOT NULL,
  -- §10.3 versioning: engine_version on every generated row enables selective
  -- re-indexing rather than a full rebuild when the model changes.
  engine_version text NOT NULL,
  -- §6.3: un-normalised, for display.
  full_text      text NOT NULL,
  -- §10.2: word-level timestamped segments. Word timing is a hard requirement —
  -- §11.1 makes citation accuracy depend on it, which is why plain Whisper is
  -- rejected in favour of WhisperX in §5.2.
  segments       jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT transcripts_segments_is_array CHECK (jsonb_typeof(segments) = 'array')
);

CREATE TRIGGER transcripts_owned_only BEFORE INSERT OR UPDATE ON transcripts
  FOR EACH ROW EXECUTE FUNCTION assert_owned_video();

-- The vector table. §6.5 decision 1: two texts are stored, not one.
-- text_normalised is what gets embedded; text_display is what the reader sees.
-- Normalising for retrieval while displaying the original is the correct
-- separation and almost no implementation does it.
--
-- §10.2 chunking: 300-600 tokens with ~50 token overlap, split on natural pauses
-- and topic shifts rather than fixed windows. Timestamps are never flattened.
CREATE TABLE transcript_chunks (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id        uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  chunk_index     integer NOT NULL CHECK (chunk_index >= 0),
  start_sec       real NOT NULL CHECK (start_sec >= 0),
  end_sec         real NOT NULL,
  speaker         text,
  text_normalised text NOT NULL,
  text_display    text NOT NULL,
  -- bge-m3 dense output is 1024-dimensional (§5.2).
  embedding       vector(1024),
  -- §10.2: pin the model version in the row. Models will change; stale rows must
  -- be identifiable.
  embedding_model text,
  token_count     integer,
  created_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT chunks_span_is_forward CHECK (end_sec > start_sec),
  CONSTRAINT chunks_embedding_has_model
    CHECK ((embedding IS NULL) = (embedding_model IS NULL)),
  UNIQUE (video_id, chunk_index)
);

CREATE TRIGGER transcript_chunks_owned_only
  BEFORE INSERT OR UPDATE ON transcript_chunks
  FOR EACH ROW EXECUTE FUNCTION assert_owned_video();

-- Semantic search (§11). Cosine distance matches the bge-m3 training objective.
CREATE INDEX transcript_chunks_embedding_idx
  ON transcript_chunks USING hnsw (embedding vector_cosine_ops);

-- Ask-video retrieves within a single video only (§11 output contract), so the
-- video_id filter comes first.
CREATE INDEX transcript_chunks_video_idx ON transcript_chunks (video_id, chunk_index);

-- §11 semantic search degrades to keyword-only when embeddings are unavailable,
-- flagged in the UI. That fallback needs a real full-text index to degrade *to*.
CREATE INDEX transcript_chunks_fts_idx
  ON transcript_chunks USING gin (to_tsvector('english', text_normalised));

-- §10.2 chapter detection: two-stage. Cosine drift between consecutive windows
-- finds boundaries; an LLM names them. Confidence is retained so §11's failure
-- mode (render an unsegmented scrubber) can be triggered on low confidence.
CREATE TABLE chapters (
  video_id      uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  chapter_index integer NOT NULL CHECK (chapter_index >= 0),
  start_sec     real NOT NULL CHECK (start_sec >= 0),
  end_sec       real NOT NULL,
  title         text NOT NULL,
  confidence    real CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (video_id, chapter_index),
  CONSTRAINT chapters_span_is_forward CHECK (end_sec > start_sec)
);

CREATE TRIGGER chapters_owned_only BEFORE INSERT OR UPDATE ON chapters
  FOR EACH ROW EXECUTE FUNCTION assert_owned_video();

-- §11 summariser contract: TL;DR of at most three sentences plus five key points,
-- each carrying a start_sec. Cached permanently, invalidated on re-transcription.
CREATE TABLE video_summaries (
  video_id     uuid PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
  model        text NOT NULL,
  tldr         text NOT NULL,
  key_points   jsonb NOT NULL DEFAULT '[]'::jsonb,
  generated_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT summaries_key_points_is_array CHECK (jsonb_typeof(key_points) = 'array')
);

CREATE TRIGGER video_summaries_owned_only
  BEFORE INSERT OR UPDATE ON video_summaries
  FOR EACH ROW EXECUTE FUNCTION assert_owned_video();

-- §6.3: doubles as the raw material for the eval set in §11.2.
CREATE TABLE ask_sessions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id   uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  user_id    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ask_turns (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      uuid NOT NULL REFERENCES ask_sessions(id) ON DELETE CASCADE,
  turn_index      integer NOT NULL CHECK (turn_index >= 0),
  question        text NOT NULL,
  answer          text,
  cited_chunk_ids uuid[] NOT NULL DEFAULT '{}',
  -- §11.1: ask-video must refuse. Threshold on retrieval score and refuse below it.
  -- Refusal rate is tracked as a headline metric — it is a feature, not a defect,
  -- so it is a stored column rather than something inferred from answer text.
  refused         boolean NOT NULL DEFAULT false,
  top_score       real,
  model           text,
  created_at      timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT ask_turns_refusal_has_no_citations
    CHECK (NOT refused OR cardinality(cited_chunk_ids) = 0),
  CONSTRAINT ask_turns_answer_or_refusal
    CHECK (refused OR answer IS NOT NULL),
  UNIQUE (session_id, turn_index)
);

CREATE INDEX ask_turns_session_idx ON ask_turns (session_id, turn_index);
