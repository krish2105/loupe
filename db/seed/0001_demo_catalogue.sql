-- Demo catalogue.
--
-- Everything here is fixture data for local development, clearly labelled so it
-- can never be mistaken for a real library. Run:
--
--   psql "$DATABASE_URL" -f db/seed/0001_demo_catalogue.sql
--
-- Shape matters more than volume. §4.1: "A platform with 2,000 items in the
-- feed and 200 deeply indexed looks like a real product with an indexing
-- backlog — which is exactly what every real platform is." So Class B
-- outnumbers Class A by roughly four to one, and a few Class A rows sit at
-- earlier pipeline stages rather than every one being conveniently `indexed`.
--
-- Idempotent: safe to re-run.

BEGIN;

-- Every Class A row points at Apple's public reference HLS stream. Real assets
-- arrive when Bunny is provisioned; until then this is what makes the player
-- exercisable end to end.
\set demo_hls '''https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/master.m3u8'''

-- ------------------------------------------------------------- channels ---
INSERT INTO channels (id, handle, name, description, source_class, external_id) VALUES
  ('00000000-0000-4000-a000-000000000001', 'mlsys',
   'MLSys Conference', 'Systems research for machine learning.', 'owned', NULL),
  ('00000000-0000-4000-a000-000000000002', 'stanford-mlsys',
   'Stanford MLSys Seminar', 'Weekly seminar on machine learning systems.', 'owned', NULL),
  ('00000000-0000-4000-a000-000000000003', 'pytorch-conf',
   'PyTorch Conference', 'Talks from the PyTorch community.', 'owned', NULL),

  ('00000000-0000-4000-b000-000000000001', 'neurips',
   'NeurIPS', 'Neural Information Processing Systems.', 'referenced', 'UC_ref_neurips'),
  ('00000000-0000-4000-b000-000000000002', 'icml',
   'ICML', 'International Conference on Machine Learning.', 'referenced', 'UC_ref_icml'),
  ('00000000-0000-4000-b000-000000000003', 'eth-zurich-dl',
   'Deep Learning Lectures', 'University lecture series.', 'referenced', 'UC_ref_ethz'),
  ('00000000-0000-4000-b000-000000000004', 'sys-ml-reading',
   'Systems + ML Reading Group', 'Paper walkthroughs.', 'referenced', 'UC_ref_srg')
ON CONFLICT (id) DO NOTHING;

-- -------------------------------------------------- Class A — owned talks ---
-- Six indexed and searchable, three still moving through the pipeline. The
-- mixture is deliberate: §5.1 says the UI must be designed for partial
-- availability, and a seed where everything is finished hides that entirely.
INSERT INTO videos
  (id, source_class, channel_id, title, description, duration_sec,
   published_at, language, processing_status, visibility)
VALUES
  ('10000000-0000-4000-a000-000000000001', 'owned', '00000000-0000-4000-a000-000000000001',
   'Attention is expensive: the quadratic bottleneck in practice',
   'Why attention cost grows with the square of sequence length, where that actually hurts in production serving, and which mitigations survive contact with real traffic.',
   3120, now() - interval '9 days', 'en', 'indexed', 'public'),

  ('10000000-0000-4000-a000-000000000002', 'owned', '00000000-0000-4000-a000-000000000001',
   'KV caching from first principles',
   'A walkthrough of key-value caching in autoregressive decoding: what is stored, what it costs in memory, and how paged attention changes the arithmetic.',
   2640, now() - interval '17 days', 'en', 'indexed', 'public'),

  ('10000000-0000-4000-a000-000000000003', 'owned', '00000000-0000-4000-a000-000000000002',
   'Memory bandwidth is the real constraint',
   'Arithmetic intensity, the roofline model, and why a faster accelerator often does not make inference faster.',
   3480, now() - interval '24 days', 'en', 'indexed', 'public'),

  ('10000000-0000-4000-a000-000000000004', 'owned', '00000000-0000-4000-a000-000000000002',
   'Evaluating retrieval without fooling yourself',
   'Building a golden set, why precision@k hides failures, and the biases that make LLM-as-judge scoring unreliable if you do not pin the judge.',
   2880, now() - interval '31 days', 'en', 'indexed', 'public'),

  ('10000000-0000-4000-a000-000000000005', 'owned', '00000000-0000-4000-a000-000000000003',
   'Chunking strategies that preserve meaning',
   'Fixed windows lose the thing you were searching for. Splitting on natural pauses and topic shifts, and why overlap is not optional.',
   2100, now() - interval '38 days', 'en', 'indexed', 'public'),

  ('10000000-0000-4000-a000-000000000006', 'owned', '00000000-0000-4000-a000-000000000003',
   'Word-level timestamps and why they matter',
   'Forced alignment, what plain transcription loses, and the downstream features that become impossible without accurate word timing.',
   1980, now() - interval '45 days', 'en', 'indexed', 'public'),

  -- Still processing. These exercise the partial-availability states.
  ('10000000-0000-4000-a000-000000000007', 'owned', '00000000-0000-4000-a000-000000000001',
   'Serving throughput under bursty load',
   'Continuous batching, queue discipline, and what tail latency does when you optimise only for the mean.',
   2760, now() - interval '2 days', 'en', 'transcribing', 'public'),

  ('10000000-0000-4000-a000-000000000008', 'owned', '00000000-0000-4000-a000-000000000002',
   'Quantisation without the cliff',
   'Where accuracy actually degrades, which layers are sensitive, and how to measure it before shipping.',
   3300, now() - interval '1 day', 'en', 'embedding', 'public'),

  ('10000000-0000-4000-a000-000000000009', 'owned', '00000000-0000-4000-a000-000000000003',
   'Speculative decoding in production',
   'Draft models, acceptance rates, and the cases where speculation costs more than it saves.',
   2400, now() - interval '4 hours', 'en', 'transcoding', 'public')
ON CONFLICT (id) DO NOTHING;

-- Media assets exist only for Class A, and only once transcoding has finished.
INSERT INTO video_assets (video_id, provider, provider_guid, hls_url, resolutions)
SELECT
  v.id,
  'demo',
  'demo-' || right(v.id::text, 12),
  :demo_hls,
  '[{"height":270},{"height":540},{"height":720},{"height":1080}]'::jsonb
FROM videos v
WHERE v.source_class = 'owned'
  AND v.processing_status NOT IN ('uploaded', 'transcoding')
ON CONFLICT (video_id) DO NOTHING;

-- --------------------------------------------- Class B — referenced feed ---
-- Breadth. Generated rather than hand-written, because the point of Class B is
-- that it is bulk metadata, not curated prose.
-- 12 topics × 4 years = 48 rows. Each topic belongs to one channel, and the
-- year suffix is how conference series actually look — the same subject
-- revisited annually.
INSERT INTO videos
  (source_class, channel_id, title, description, duration_sec,
   published_at, processing_status, visibility, external_id)
WITH refs AS (
  SELECT id, handle, (row_number() OVER (ORDER BY handle) - 1)::int AS idx
  FROM channels
  WHERE source_class = 'referenced'
),
topics AS (
  SELECT title, (row_number() OVER () - 1)::int AS idx
  FROM (VALUES
    ('Scaling laws revisited'),
    ('Sparse mixtures in practice'),
    ('Long-context retrieval'),
    ('Distributed training at scale'),
    ('Optimiser stability at billion-parameter scale'),
    ('Data curation for pretraining'),
    ('Inference on commodity hardware'),
    ('Learning from human feedback'),
    ('Structured generation and constrained decoding'),
    ('Vector index tradeoffs'),
    ('Streaming architectures for online learning'),
    ('Reproducibility in machine learning research')
  ) AS t(title)
)
SELECT
  'referenced',
  r.id,
  tp.title || ' (' || (2022 + y.n) || ')',
  'Conference recording. Metadata only — this talk is not indexed for search inside.',
  1200 + ((tp.idx * 137 + y.n * 311) % 4200),
  now() - (((tp.idx * 9) + (3 - y.n) * 400 + 6) || ' days')::interval,
  'referenced_only',
  'public',
  'ref_' || r.handle || '_' || tp.idx || '_' || y.n
FROM topics tp
JOIN refs r ON r.idx = tp.idx % (SELECT count(*) FROM refs)
CROSS JOIN generate_series(0, 3) AS y(n)
ON CONFLICT (source_class, external_id) DO NOTHING;

-- ------------------------------------------------------------- statistics ---
INSERT INTO video_stats (video_id, view_count, like_count, comment_count)
SELECT
  v.id,
  -- Deterministic but uneven, so the grid does not look generated.
  (('x' || substr(md5(v.id::text), 1, 6))::bit(24)::int % 84000) + 120,
  (('x' || substr(md5(v.id::text || 'l'), 1, 5))::bit(20)::int % 2400),
  0
FROM videos v
ON CONFLICT (video_id) DO NOTHING;

-- --------------------------------------------------------------- people ----
-- Demo accounts, so comments have authors before anyone has signed up.
--
-- Skipped entirely on a hosted Supabase project. There, users.id carries a
-- foreign key to auth.users and rows are created by a trigger when someone
-- signs up, so inventing three of them here fails with
--
--   insert or update on table "users" violates foreign key constraint
--   "users_id_fkey"
--
-- which is the constraint doing its job. The check is on the constraint rather
-- than on a flag someone has to pass, because the environment already knows
-- which kind it is and a flag is a thing to forget.
DO $seed$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'users_id_fkey'
      AND conrelid = 'public.users'::regclass
  ) THEN
    RAISE NOTICE 'Hosted project: skipping demo accounts and their comments. Real accounts come from auth.users.';
    RETURN;
  END IF;

  INSERT INTO users (id, handle, display_name) VALUES
    ('20000000-0000-4000-a000-000000000001', 'demo-priya', 'Priya'),
    ('20000000-0000-4000-a000-000000000002', 'demo-sam',   'Sam'),
    ('20000000-0000-4000-a000-000000000003', 'demo-yusuf', 'Yusuf')
  ON CONFLICT (id) DO NOTHING;

  INSERT INTO comments (id, video_id, user_id, parent_id, body, created_at) VALUES
    ('30000000-0000-4000-a000-000000000001', '10000000-0000-4000-a000-000000000001',
     '20000000-0000-4000-a000-000000000001', NULL,
     'The section on where the quadratic term stops mattering in practice was worth the whole talk.',
     now() - interval '6 days'),
    ('30000000-0000-4000-a000-000000000002', '10000000-0000-4000-a000-000000000001',
     '20000000-0000-4000-a000-000000000002', '30000000-0000-4000-a000-000000000001',
     'Agreed — it is the part everyone skips when they summarise this.',
     now() - interval '5 days'),
    ('30000000-0000-4000-a000-000000000003', '10000000-0000-4000-a000-000000000001',
     '20000000-0000-4000-a000-000000000003', NULL,
     'Does the batching argument still hold with paged attention? Curious how much of this changes.',
     now() - interval '3 days'),
    ('30000000-0000-4000-a000-000000000004', '10000000-0000-4000-a000-000000000003',
     '20000000-0000-4000-a000-000000000002', NULL,
     'The roofline walkthrough is the clearest explanation of this I have found.',
     now() - interval '11 days')
  ON CONFLICT (id) DO NOTHING;
END;
$seed$;

UPDATE video_stats s
SET comment_count = (SELECT count(*) FROM comments c WHERE c.video_id = s.video_id);

COMMIT;

\echo 'Seeded. Counts:'
SELECT source_class::text, processing_status::text, count(*)
FROM videos GROUP BY 1, 2 ORDER BY 1, 2;
