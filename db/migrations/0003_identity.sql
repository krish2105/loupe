-- 0003 — identity and relationships
-- Plan ref: §6.2. The four "list" surfaces are one abstraction with different
-- semantics: subscriptions, watch_events, saved_items, and playlists. Built once.

-- Profile table. On Supabase this is populated from auth.users by a trigger; the id
-- is the auth user id. Locally it stands alone so the schema runs without GoTrue.
-- See db/migrations/supabase/0001_auth_link.sql for the hosted-only foreign key.
CREATE TABLE users (
  id           uuid PRIMARY KEY,
  handle       text NOT NULL UNIQUE,
  display_name text NOT NULL,
  avatar_url   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER users_touch BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Serves: Subscriptions surface, Notifications fan-out.
CREATE TABLE subscriptions (
  user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel_id     uuid NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
  notify_enabled boolean NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, channel_id)
);

-- Fan-out on write (§6.2) reads subscribers of a channel.
CREATE INDEX subscriptions_channel_idx
  ON subscriptions (channel_id) WHERE notify_enabled;

-- §6.5 decision 2: append-only, never mutated. Resume position is a read-side
-- aggregate, not a column that gets overwritten. This is what makes the
-- recommendation model trainable later without a schema migration.
CREATE TABLE watch_events (
  id           bigserial PRIMARY KEY,
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id     uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  position_sec integer NOT NULL CHECK (position_sec >= 0),
  watch_pct    real NOT NULL CHECK (watch_pct >= 0 AND watch_pct <= 1),
  completed    boolean NOT NULL DEFAULT false,
  occurred_at  timestamptz NOT NULL DEFAULT now(),
  -- §12.2: synthetic histories must be distinguishable from real ones at query
  -- time, not just in the README. Never present synthetic results as real data.
  is_synthetic boolean NOT NULL DEFAULT false
);

CREATE TRIGGER watch_events_append_only
  BEFORE UPDATE OR DELETE ON watch_events
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();

-- History surface, and the resume lookup in §9.1.
CREATE INDEX watch_events_user_time_idx
  ON watch_events (user_id, occurred_at DESC);
CREATE INDEX watch_events_user_video_time_idx
  ON watch_events (user_id, video_id, occurred_at DESC);

-- Serves: Watch Later, Liked. One table, two semantics.
CREATE TABLE saved_items (
  user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id  uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  list_type saved_list_type NOT NULL,
  added_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, video_id, list_type)
);

CREATE INDEX saved_items_user_list_idx
  ON saved_items (user_id, list_type, added_at DESC);

CREATE TABLE playlists (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title        text NOT NULL,
  description  text,
  visibility   visibility_level NOT NULL DEFAULT 'private',
  -- §11 AI playlists: the ordering rationale is part of the output contract, so it
  -- is stored with the playlist rather than regenerated on read.
  generated_by playlist_origin NOT NULL DEFAULT 'user',
  rationale    text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT playlists_ai_has_rationale
    CHECK (generated_by <> 'ai' OR rationale IS NOT NULL)
);

CREATE TRIGGER playlists_touch BEFORE UPDATE ON playlists
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE playlist_items (
  playlist_id uuid NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
  video_id    uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  position    integer NOT NULL CHECK (position >= 0),
  added_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (playlist_id, video_id),
  UNIQUE (playlist_id, position) DEFERRABLE INITIALLY DEFERRED
);

-- §6.2: one reply level only.
CREATE TABLE comments (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  video_id   uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  parent_id  uuid REFERENCES comments(id) ON DELETE CASCADE,
  body       text NOT NULL CHECK (length(btrim(body)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  edited_at  timestamptz
);

CREATE OR REPLACE FUNCTION enforce_single_reply_level() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.parent_id IS NOT NULL
     AND EXISTS (SELECT 1 FROM comments WHERE id = NEW.parent_id AND parent_id IS NOT NULL)
  THEN
    RAISE EXCEPTION 'comments support one reply level only (plan §6.2)';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER comments_single_reply_level
  BEFORE INSERT OR UPDATE ON comments
  FOR EACH ROW EXECUTE FUNCTION enforce_single_reply_level();

CREATE INDEX comments_video_idx ON comments (video_id, created_at DESC);
CREATE INDEX comments_parent_idx ON comments (parent_id) WHERE parent_id IS NOT NULL;

-- §6.2: fan-out on write.
CREATE TABLE notifications (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind       notification_kind NOT NULL,
  actor_id   uuid REFERENCES users(id) ON DELETE SET NULL,
  target_id  uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  read_at    timestamptz
);

CREATE INDEX notifications_unread_idx
  ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;
