-- Schema constraint tests.
--
-- The migrations claim, in comments, that the plan's rules are enforced by the
-- database rather than by convention. This file proves it. Everything runs inside
-- one transaction and rolls back, so it is safe against a live dev database.
--
-- Run:  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/tests/constraints.sql

BEGIN;

CREATE OR REPLACE FUNCTION assert_rejects(stmt text, label text) RETURNS void
LANGUAGE plpgsql AS $fn$
BEGIN
  BEGIN
    EXECUTE stmt;
  EXCEPTION WHEN others THEN
    RAISE NOTICE 'PASS   %', label;
    RETURN;
  END;
  RAISE EXCEPTION 'FAIL   % — statement was accepted but should have been rejected', label;
END;
$fn$;

CREATE OR REPLACE FUNCTION assert_accepts(stmt text, label text) RETURNS void
LANGUAGE plpgsql AS $fn$
BEGIN
  EXECUTE stmt;
  RAISE NOTICE 'PASS   %', label;
EXCEPTION WHEN others THEN
  RAISE EXCEPTION 'FAIL   % — rejected with: %', label, SQLERRM;
END;
$fn$;

-- ---------------------------------------------------------------- fixtures ---
INSERT INTO channels (id, handle, name, source_class, external_id) VALUES
  ('11111111-1111-1111-1111-111111111111', 'owned-ch', 'Owned Channel', 'owned', NULL),
  ('22222222-2222-2222-2222-222222222222', 'ref-ch',   'Referenced',    'referenced', 'UC_ext_1');

INSERT INTO videos (id, source_class, channel_id, title, processing_status, external_id) VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'owned', '11111111-1111-1111-1111-111111111111',
   'An owned conference talk', 'indexed', NULL),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'referenced', '22222222-2222-2222-2222-222222222222',
   'A referenced talk', 'referenced_only', 'ext_vid_1');

INSERT INTO users (id, handle, display_name) VALUES
  ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'krish', 'Krishna');

-- ------------------------------------------- §4 — the capability asymmetry ---
SELECT assert_rejects($$
  INSERT INTO transcripts (video_id, language, engine, engine_version, full_text)
  VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'en', 'whisperx', '3.1.1', 'text')
$$, '§4  Class B cannot hold a transcript');

SELECT assert_rejects($$
  INSERT INTO transcript_chunks (video_id, chunk_index, start_sec, end_sec, text_normalised, text_display)
  VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 0, 0, 10, 'a', 'a')
$$, '§4  Class B cannot hold transcript chunks');

SELECT assert_rejects($$
  INSERT INTO video_assets (video_id, provider, provider_guid)
  VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'bunny', 'guid-1')
$$, '§4  Class B cannot hold a media asset');

SELECT assert_rejects($$
  UPDATE videos SET processing_status = 'transcribing'
  WHERE id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
$$, '§4  Class B cannot enter the pipeline');

SELECT assert_rejects($$
  INSERT INTO videos (source_class, channel_id, title, external_id)
  VALUES ('referenced', '22222222-2222-2222-2222-222222222222', 'No external id', NULL)
$$, '§4  Class B requires an external id');

SELECT assert_accepts($$
  INSERT INTO transcripts (video_id, language, engine, engine_version, full_text)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'en', 'whisperx', '3.1.1', 'the real text')
$$, '§4  Class A can hold a transcript');

-- ------------------------------------------ §13 — shorts are playable ---
-- A vertical feed autoplays. Class B content cannot be played by Loupe at all,
-- so a referenced short would be an unplayable card in an autoplaying feed.
SELECT assert_rejects($$
  UPDATE videos SET is_short = true
  WHERE id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
$$, '§13  a referenced video cannot be a short');

SELECT assert_accepts($$
  UPDATE videos SET is_short = true
  WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
$$, '§13  an owned video can be a short');

-- ------------------------------------ §6.5 — watch_events is append-only ---
INSERT INTO watch_events (user_id, video_id, position_sec, watch_pct)
VALUES ('cccccccc-cccc-cccc-cccc-cccccccccccc', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 42, 0.35);

SELECT assert_rejects($$
  UPDATE watch_events SET position_sec = 99
  WHERE user_id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
$$, '§6.5 watch_events rejects UPDATE');

SELECT assert_rejects($$
  DELETE FROM watch_events WHERE user_id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'
$$, '§6.5 watch_events rejects DELETE');

-- 0007: append-only must not make account deletion impossible. A row-level
-- DELETE trigger fires on cascades too, so this is tested on a throwaway video
-- rather than the one later assertions depend on.
INSERT INTO videos (id, source_class, channel_id, title, processing_status) VALUES
  ('a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1', 'owned',
   '11111111-1111-1111-1111-111111111111', 'Doomed talk', 'indexed');
INSERT INTO watch_events (user_id, video_id, position_sec, watch_pct)
VALUES ('cccccccc-cccc-cccc-cccc-cccccccccccc',
        'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1', 30, 0.2);

SELECT assert_rejects($$
  DELETE FROM videos WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'
$$, '0007 a cascading delete is blocked without the purge opt-in');

SELECT set_config('loupe.allow_purge', 'on', true);

SELECT assert_rejects($$
  UPDATE watch_events SET position_sec = 1
  WHERE video_id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'
$$, '0007 UPDATE stays blocked even during an authorised purge');

SELECT assert_accepts($$
  DELETE FROM videos WHERE id = 'a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1'
$$, '0007 an authorised purge cascades successfully');

SELECT set_config('loupe.allow_purge', 'off', true);

-- --------------------------------------- §6.2 — one comment reply level ---
INSERT INTO comments (id, video_id, user_id, body) VALUES
  ('dddddddd-dddd-dddd-dddd-dddddddddddd', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
   'cccccccc-cccc-cccc-cccc-cccccccccccc', 'top level');
INSERT INTO comments (id, video_id, user_id, parent_id, body) VALUES
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
   'cccccccc-cccc-cccc-cccc-cccccccccccc', 'dddddddd-dddd-dddd-dddd-dddddddddddd', 'first reply');

SELECT assert_rejects($$
  INSERT INTO comments (video_id, user_id, parent_id, body)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'cccccccc-cccc-cccc-cccc-cccccccccccc',
          'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee', 'reply to a reply')
$$, '§6.2 comments reject a second reply level');

-- ------------------------------------------- §5.1 — pipeline idempotency ---
INSERT INTO pipeline_jobs (video_id, stage, version)
VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'transcribing', 1);

SELECT assert_rejects($$
  INSERT INTO pipeline_jobs (video_id, stage, version)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'transcribing', 1)
$$, '§5.1 pipeline job (video, stage, version) is unique');

SELECT assert_accepts($$
  INSERT INTO pipeline_jobs (video_id, stage, version)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'transcribing', 2)
$$, '§5.1 a new version of the same stage is allowed');

-- ----------------------------------------- §11.1 — ask-video must refuse ---
INSERT INTO ask_sessions (id, video_id) VALUES
  ('ffffffff-ffff-ffff-ffff-ffffffffffff', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa');

SELECT assert_rejects($$
  INSERT INTO ask_turns (session_id, turn_index, question, refused, cited_chunk_ids)
  VALUES ('ffffffff-ffff-ffff-ffff-ffffffffffff', 0, 'q', true,
          ARRAY['aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa']::uuid[])
$$, '§11.1 a refusal cannot carry citations');

SELECT assert_rejects($$
  INSERT INTO ask_turns (session_id, turn_index, question, refused, answer)
  VALUES ('ffffffff-ffff-ffff-ffff-ffffffffffff', 1, 'q', false, NULL)
$$, '§11.1 a non-refusal must carry an answer');

-- ------------------------------------ §10.2 — embeddings pin their model ---
SELECT assert_rejects($$
  INSERT INTO transcript_chunks
    (video_id, chunk_index, start_sec, end_sec, text_normalised, text_display, embedding)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 0, 0, 10, 'a', 'a',
          array_fill(0.1::real, ARRAY[1024])::vector)
$$, '§10.2 an embedding without embedding_model is rejected');

SELECT assert_rejects($$
  INSERT INTO transcript_chunks
    (video_id, chunk_index, start_sec, end_sec, text_normalised, text_display)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 1, 30, 10, 'a', 'a')
$$, '§10.2 a chunk whose span runs backwards is rejected');

SELECT assert_accepts($$
  INSERT INTO transcript_chunks
    (video_id, chunk_index, start_sec, end_sec, text_normalised, text_display,
     embedding, embedding_model)
  VALUES ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 2, 0, 10, 'normalised', 'Display!',
          array_fill(0.1::real, ARRAY[1024])::vector, 'bge-m3')
$$, '§10.2 a properly versioned embedded chunk is accepted');

ROLLBACK;
