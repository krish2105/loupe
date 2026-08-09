-- 0008 — shorts
-- Plan refs: §3.1 (Shorts is one of the eleven surfaces), §13
--
-- An explicit flag rather than a derived rule.
--
-- The obvious alternative is to derive it: short duration plus a vertical
-- aspect ratio. That fails on both halves. Aspect ratio is not stored — it
-- lives in the provider's rendition ladder, so deriving it means a join and a
-- jsonb lookup on every feed query. And duration alone is wrong: a 50-second
-- landscape clip is not a short, and treating it as one puts letterboxed
-- content in a vertical feed.
--
-- A column also lets a person decide. Whether something belongs in the vertical
-- feed is an editorial judgement, not a property of the file.

ALTER TABLE videos
  ADD COLUMN is_short boolean NOT NULL DEFAULT false;

-- The shorts feed reads only this, newest first, so it gets its own index
-- rather than filtering the main feed index.
CREATE INDEX videos_shorts_idx
  ON videos (published_at DESC NULLS LAST)
  WHERE is_short AND visibility = 'public';

-- §4 again: a vertical feed autoplays, and Class B content cannot be played by
-- Loupe at all — it lives at its original source. A referenced short would be
-- an unplayable card in an autoplaying feed, which is worse than absent.
ALTER TABLE videos
  ADD CONSTRAINT videos_shorts_are_owned
  CHECK (NOT is_short OR source_class = 'owned');
