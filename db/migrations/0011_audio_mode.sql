-- 0011 — audio mode
-- Plan refs: ADR 0003, docs/design/audio-data-model.md.
--
-- One enum column, not a parallel tracks/albums/artists schema. The reasoning
-- is in the design note and the short version is that spoken audio has none of
-- the metadata that justifies a separate music model: no track numbers, no
-- album artist, no featured artists, no ISRC. A podcast is a show with episodes
-- in order, which is a channel with videos ordered by published_at, and both of
-- those already exist and already work.
--
-- Of the nine surfaces audio mode needs, eight require no schema change at all.
-- This migration is the ninth.

CREATE TYPE content_kind AS ENUM ('video', 'audio');

-- Defaulted, so every existing row is correct without a backfill and every
-- existing query keeps working untouched.
ALTER TABLE videos
  ADD COLUMN content_kind content_kind NOT NULL DEFAULT 'video';

CREATE INDEX videos_audio_feed_idx
  ON videos (content_kind, published_at DESC NULLS LAST)
  WHERE visibility = 'public';

-- No `downloads` table. ADR 0003 scoped offline downloads and this migration
-- deliberately does not prepare for them, because the feature is not built:
-- every piece of media in the catalogue is a third-party reference stream, and
-- the ADR is explicit that caching content Loupe neither owns nor holds an open
-- licence for is a licensing fact rather than a technical gap. A table nothing
-- writes to is a claim that something does.
