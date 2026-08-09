-- Demo spoken audio.
--
-- Run after 0001:
--   psql "$DATABASE_URL" -f db/seed/0003_audio.sql
--   cd services/pipeline && uv run python -m app.run --all
--
-- Unlike the shorts seed, these land at `transcoded` rather than `enriched`,
-- because audio mode's whole argument (ADR 0003) is that spoken audio is the
-- shape this product was already built for. An episode with no transcript
-- would have a time-synced transcript view with nothing to sync, so these go
-- through the pipeline like any other Class A content.
--
-- Two things stated rather than discovered:
--
-- The media behind these is the same reference HLS stream everything else
-- uses, and it has no speech in it. So the transcripts are fixture output, the
-- same limitation the README already records for the owned catalogue.
--
-- The stream is a video stream. Audio mode renders no visual surface, but the
-- element underneath is still a <video> element, because that is what plays
-- HLS in every browser. An audio-only rendition would travel the identical
-- code path; there is simply no audio-only test stream to point at.

BEGIN;

-- The same reference stream as 0001, and see that file for why it is Mux's
-- rather than Apple's: the Apple demo serves CORS headers on only some of
-- its renditions from some edges, which breaks hls.js and nothing else.
\set demo_hls '''https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8'''

-- Shows are channels. A podcast has a show, episodes in order, and publication
-- dates, which is exactly what channels and videos already are.
INSERT INTO channels (id, handle, name, description, source_class, external_id) VALUES
  ('00000000-0000-4000-c000-000000000001', 'inference-hour',
   'The Inference Hour', 'Long-form conversations about putting models in production.',
   'owned', NULL),
  ('00000000-0000-4000-c000-000000000002', 'reading-group',
   'Papers, Out Loud', 'One paper per episode, read and argued about.',
   'owned', NULL)
ON CONFLICT (id) DO NOTHING;

INSERT INTO videos
  (id, source_class, content_kind, channel_id, title, description, duration_sec,
   published_at, language, processing_status, visibility)
VALUES
  ('12000000-0000-4000-a000-000000000001', 'owned', 'audio',
   '00000000-0000-4000-c000-000000000001',
   'Serving is a queueing problem',
   'Why throughput graphs lie, and what tail latency does to a batching scheduler.',
   2760, now() - interval '3 days', 'en', 'transcoded', 'public'),
  ('12000000-0000-4000-a000-000000000002', 'owned', 'audio',
   '00000000-0000-4000-c000-000000000001',
   'The quantisation conversation nobody enjoys',
   'Which layers are sensitive, why the average metric hides it, and what to measure instead.',
   3180, now() - interval '10 days', 'en', 'transcoded', 'public'),
  ('12000000-0000-4000-a000-000000000003', 'owned', 'audio',
   '00000000-0000-4000-c000-000000000001',
   'Everything is memory bandwidth',
   'An hour on arithmetic intensity and the accelerator that did not help.',
   3600, now() - interval '17 days', 'en', 'transcoded', 'public'),
  ('12000000-0000-4000-a000-000000000004', 'owned', 'audio',
   '00000000-0000-4000-c000-000000000002',
   'Attention is all you need, revisited',
   'Reading the 2017 paper again with eight years of hindsight.',
   2940, now() - interval '5 days', 'en', 'transcoded', 'public'),
  ('12000000-0000-4000-a000-000000000005', 'owned', 'audio',
   '00000000-0000-4000-c000-000000000002',
   'Retrieval evaluation, and how to fool yourself',
   'Why precision@5 on your own golden set is not evidence of anything.',
   2520, now() - interval '12 days', 'en', 'transcoded', 'public'),
  ('12000000-0000-4000-a000-000000000006', 'owned', 'audio',
   '00000000-0000-4000-c000-000000000002',
   'Chunking, and the boundary problem',
   'Fixed windows, natural pauses, and what a bad split costs downstream.',
   2280, now() - interval '19 days', 'en', 'transcoded', 'public')
ON CONFLICT (id) DO NOTHING;

INSERT INTO video_assets (video_id, provider, provider_guid, hls_url, resolutions)
SELECT v.id, 'demo', 'audio-' || right(v.id::text, 12), :demo_hls,
       '[{"height":720}]'::jsonb
FROM videos v
WHERE v.content_kind = 'audio'
ON CONFLICT (video_id) DO NOTHING;

INSERT INTO video_stats (video_id, view_count, like_count, comment_count)
SELECT v.id,
       (('x' || substr(md5(v.id::text), 1, 6))::bit(24)::int % 40000) + 400,
       (('x' || substr(md5(v.id::text || 'l'), 1, 5))::bit(20)::int % 2000),
       0
FROM videos v
WHERE v.content_kind = 'audio'
ON CONFLICT (video_id) DO NOTHING;

COMMIT;

\echo 'Audio seeded. Run the pipeline to index it:'
SELECT count(*) AS episodes, count(DISTINCT channel_id) AS shows
FROM videos WHERE content_kind = 'audio';
