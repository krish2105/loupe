-- Supabase-only: bind public.users to auth.users and enable row-level security.
-- Plan ref: §5.2 (Supabase Auth — four surfaces depend on real user identity).
--
-- Not part of the numbered migrations because the auth schema only exists on a
-- hosted Supabase project. Local development runs against plain Postgres.

ALTER TABLE users
  ADD CONSTRAINT users_id_fkey
  FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- A profile row is created for every new auth user. Doing this in the database
-- rather than the app means a user can never exist without a profile, whichever
-- sign-up route they arrive through.
CREATE OR REPLACE FUNCTION handle_new_auth_user() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO public.users (id, handle, display_name)
  VALUES (
    NEW.id,
    -- Local part of the email, deduplicated with a short suffix on collision.
    split_part(NEW.email, '@', 1) || '-' || substr(NEW.id::text, 1, 4),
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1))
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_auth_user();

-- Row-level security on the user-owned tables. The catalogue itself (videos,
-- channels, transcripts) is world-readable; a person's history is not.
ALTER TABLE users          ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_events   ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_items    ENABLE ROW LEVEL SECURITY;
ALTER TABLE playlists      ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications  ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_read_all   ON users FOR SELECT USING (true);
CREATE POLICY users_write_self ON users FOR UPDATE USING (auth.uid() = id);

CREATE POLICY subs_own ON subscriptions
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- §6.5: watch_events is append-only. RLS grants insert and select, never update
-- or delete — which matches the trigger rather than duplicating it.
CREATE POLICY watch_read_own   ON watch_events FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY watch_insert_own ON watch_events FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY saved_own ON saved_items
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY playlists_read ON playlists
  FOR SELECT USING (visibility = 'public' OR auth.uid() = owner_id);
CREATE POLICY playlists_write ON playlists
  FOR ALL USING (auth.uid() = owner_id) WITH CHECK (auth.uid() = owner_id);

CREATE POLICY notifications_own ON notifications
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
