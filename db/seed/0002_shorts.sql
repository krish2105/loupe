-- Demo shorts.
--
-- Fixture data, like 0001. Run after it:
--   psql "$DATABASE_URL" -f db/seed/0002_shorts.sql
--
-- These are marked `enriched` with assets attached rather than being pushed
-- through the pipeline. A sixty-second clip produces two or three chunks,
-- which is below the floor for chapter detection and summarising anyway — so
-- running them through would add pipeline noise without producing anything the
-- UI would show.
--
-- Known limitation, stated rather than discovered: the media behind these is
-- the same 16:9 reference stream everything else uses. The feed is built for
-- 9:16 and the player crops to fill, which is what a real client does with
-- mismatched aspect — but these are not genuinely vertical videos.

BEGIN;

\set demo_hls '''https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/master.m3u8'''

INSERT INTO videos
  (id, source_class, channel_id, title, description, duration_sec,
   published_at, language, processing_status, visibility, is_short)
VALUES
  ('11000000-0000-4000-a000-000000000001', 'owned', '00000000-0000-4000-a000-000000000001',
   'The quadratic term, in sixty seconds', 'Why attention cost grows with the square of sequence length.',
   58, now() - interval '2 hours', 'en', 'enriched', 'public', true),
  ('11000000-0000-4000-a000-000000000002', 'owned', '00000000-0000-4000-a000-000000000001',
   'Roofline, explained fast', 'Where your kernel actually sits on the roofline.',
   47, now() - interval '9 hours', 'en', 'enriched', 'public', true),
  ('11000000-0000-4000-a000-000000000003', 'owned', '00000000-0000-4000-a000-000000000002',
   'What the KV cache actually stores', 'Keys and values, and why recomputing them is the waste.',
   62, now() - interval '1 day', 'en', 'enriched', 'public', true),
  ('11000000-0000-4000-a000-000000000004', 'owned', '00000000-0000-4000-a000-000000000002',
   'Continuous batching in one minute', 'Admitting requests as slots free up.',
   55, now() - interval '2 days', 'en', 'enriched', 'public', true),
  ('11000000-0000-4000-a000-000000000005', 'owned', '00000000-0000-4000-a000-000000000003',
   'Why a faster GPU did not help', 'Memory bandwidth, not arithmetic.',
   41, now() - interval '3 days', 'en', 'enriched', 'public', true),
  ('11000000-0000-4000-a000-000000000006', 'owned', '00000000-0000-4000-a000-000000000003',
   'Speculative decoding, briefly', 'Draft models and acceptance rates.',
   66, now() - interval '4 days', 'en', 'enriched', 'public', true),
  ('11000000-0000-4000-a000-000000000007', 'owned', '00000000-0000-4000-a000-000000000001',
   'Quantisation: where it breaks', 'Which layers are sensitive, and how to tell.',
   52, now() - interval '5 days', 'en', 'enriched', 'public', true),
  ('11000000-0000-4000-a000-000000000008', 'owned', '00000000-0000-4000-a000-000000000002',
   'Tokenisation costs you later', 'A downstream cost nobody budgets for.',
   49, now() - interval '6 days', 'en', 'enriched', 'public', true)
ON CONFLICT (id) DO NOTHING;

INSERT INTO video_assets (video_id, provider, provider_guid, hls_url, resolutions)
SELECT v.id, 'demo', 'short-' || right(v.id::text, 12), :demo_hls,
       '[{"height":720},{"height":1080}]'::jsonb
FROM videos v
WHERE v.is_short
ON CONFLICT (video_id) DO NOTHING;

INSERT INTO video_stats (video_id, view_count, like_count, comment_count)
SELECT v.id,
       (('x' || substr(md5(v.id::text), 1, 6))::bit(24)::int % 240000) + 800,
       (('x' || substr(md5(v.id::text || 'l'), 1, 5))::bit(20)::int % 9000),
       0
FROM videos v
WHERE v.is_short
ON CONFLICT (video_id) DO NOTHING;

COMMIT;

\echo 'Shorts seeded:'
SELECT count(*) AS shorts FROM videos WHERE is_short;
