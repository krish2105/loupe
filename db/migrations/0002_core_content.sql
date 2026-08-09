-- 0002 — core content
-- Plan ref: §6.1

CREATE TABLE channels (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  handle       text NOT NULL UNIQUE,
  name         text NOT NULL,
  avatar_url   text,
  banner_url   text,
  description  text,
  source_class source_class NOT NULL,
  -- §6.1: referenced channels are synthetic records, not real users. external_id is
  -- the upstream channel identifier and is required for Class B.
  external_id  text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT channels_referenced_has_external_id
    CHECK (source_class <> 'referenced' OR external_id IS NOT NULL),
  UNIQUE (source_class, external_id)
);

CREATE TABLE videos (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_class      source_class NOT NULL,
  external_id       text,
  channel_id        uuid NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
  title             text NOT NULL,
  description       text,
  duration_sec      integer CHECK (duration_sec IS NULL OR duration_sec >= 0),
  published_at      timestamptz,
  -- §10.3 language handling: detected and stored per video.
  language          text,
  processing_status processing_status NOT NULL DEFAULT 'uploaded',
  -- §10.1: failures park at failed_<stage> with a retry count.
  retry_count       integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
  visibility        visibility_level NOT NULL DEFAULT 'public',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),

  -- §4: the capability asymmetry, enforced rather than remembered.
  CONSTRAINT videos_referenced_never_processes
    CHECK (source_class <> 'referenced' OR processing_status = 'referenced_only'),
  CONSTRAINT videos_owned_never_referenced_only
    CHECK (source_class <> 'owned' OR processing_status <> 'referenced_only'),
  CONSTRAINT videos_referenced_has_external_id
    CHECK (source_class <> 'referenced' OR external_id IS NOT NULL),
  UNIQUE (source_class, external_id)
);

CREATE INDEX videos_channel_published_idx
  ON videos (channel_id, published_at DESC NULLS LAST);
-- Serves the pipeline dashboard in §14 (video counts per stage).
CREATE INDEX videos_status_idx ON videos (processing_status);
-- Feed assembly reads public videos newest-first.
CREATE INDEX videos_feed_idx
  ON videos (published_at DESC NULLS LAST)
  WHERE visibility = 'public';

CREATE TRIGGER videos_touch BEFORE UPDATE ON videos
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER channels_touch BEFORE UPDATE ON channels
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- §6.1: Class A only. The media service is the sole holder of provider credentials
-- (§5), so this table stores only what playback needs.
CREATE TABLE video_assets (
  video_id             uuid PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
  provider             text NOT NULL,
  provider_guid        text NOT NULL,
  hls_url              text,
  thumbnail_sprite_url text,
  sprite_interval_sec  integer,
  -- Rendition ladder as reported by the provider webhook.
  resolutions          jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at           timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT video_assets_resolutions_is_array
    CHECK (jsonb_typeof(resolutions) = 'array'),
  UNIQUE (provider, provider_guid)
);

CREATE TRIGGER video_assets_owned_only BEFORE INSERT OR UPDATE ON video_assets
  FOR EACH ROW EXECUTE FUNCTION assert_owned_video();

-- §6.1: denormalised counters, updated asynchronously. Never authoritative;
-- watch_events is the source of truth for views.
CREATE TABLE video_stats (
  video_id      uuid PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
  view_count    bigint NOT NULL DEFAULT 0 CHECK (view_count >= 0),
  like_count    bigint NOT NULL DEFAULT 0 CHECK (like_count >= 0),
  comment_count bigint NOT NULL DEFAULT 0 CHECK (comment_count >= 0),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
