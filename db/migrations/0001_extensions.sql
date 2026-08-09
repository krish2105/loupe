-- 0001 — extensions and shared enums
-- Plan refs: §4 (content classes), §5.1 (single source of truth for state), §10.1 (stage machine)

CREATE EXTENSION IF NOT EXISTS vector;    -- transcript_chunks.embedding
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

-- §4. Two content classes with different capability sets, treated as a first-class
-- domain concept. This column drives every downstream capability decision, so it is
-- an enum on the row rather than a boolean or an inferred join.
CREATE TYPE source_class AS ENUM ('owned', 'referenced');

-- §10.1. Explicit, resumable stage machine. Failures park at failed_<stage> and carry
-- a retry count on videos. §5.1 requires one status enum per video, not a scatter of
-- boolean flags. 'referenced_only' is the terminal state for Class B, which never
-- enters the pipeline at all.
CREATE TYPE processing_status AS ENUM (
  'referenced_only',
  'uploaded',
  'transcoding',   'failed_transcoding',
  'transcoded',
  'transcribing',  'failed_transcribing',
  'transcribed',
  'chunking',      'failed_chunking',
  'embedding',     'failed_embedding',
  'indexed',
  'enriched'
);

CREATE TYPE visibility_level  AS ENUM ('public', 'unlisted', 'private');
CREATE TYPE saved_list_type   AS ENUM ('watch_later', 'liked');
CREATE TYPE playlist_origin   AS ENUM ('user', 'ai');
CREATE TYPE notification_kind AS ENUM ('new_upload', 'reply', 'mention');

-- §6.5 decision 2: watch_events is append-only and never mutated. Enforced in the
-- database rather than by convention, because the recsys training set depends on it.
CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only (plan §6.5); % rejected', TG_TABLE_NAME, TG_OP;
END;
$$;

-- §4.2 rule 3. The capability gap between Class A and Class B is a legitimate
-- architectural fact, so the schema refuses to let Class B acquire Class A artifacts.
-- Without this the asymmetry survives only as long as everyone remembers it.
CREATE OR REPLACE FUNCTION assert_owned_video() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF (SELECT source_class FROM videos WHERE id = NEW.video_id) <> 'owned' THEN
    RAISE EXCEPTION
      '%: only Class A (owned) videos may hold rows in this table (plan §4)',
      TG_TABLE_NAME;
  END IF;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;
