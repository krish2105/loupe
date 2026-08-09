-- 0012 — offline downloads
-- Plan ref: ADR 0003 ("Offline playback as a PWA with a service worker").
--
-- 0011 deliberately did not create this table, on the reasoning that ADR 0003
-- limits offline downloads to content Loupe owns or that is openly licensed,
-- and that every piece of media in the catalogue is a third-party stream. That
-- reasoning conflated two different things and this migration corrects it.
--
-- The ADR's rule is about the *class of content*, and the schema can enforce
-- exactly that: Class A is what Loupe owns, Class B is referenced and never
-- stored. So downloads are constrained to Class A here, in the database, rather
-- than being declined wholesale in a code comment. The demo catalogue's media
-- being a developer test stream is a fixture limitation, recorded in the README
-- with the rest of them, not a reason to leave the capability unbuilt.
--
-- This table records intent and accounting. The audio itself lives in the
-- browser's Cache Storage on the device, because that is the only place a
-- service worker can serve it from. The row is what lets the library say
-- "downloaded" before the cache has been opened, what a second device would
-- read to offer the same downloads, and what an eviction policy would sort by.

CREATE TABLE downloads (
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id     uuid NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
  requested_at timestamptz NOT NULL DEFAULT now(),
  -- Written when the transfer completes, so a null here means "started and
  -- never finished" rather than "finished, size unknown". That distinction is
  -- what lets the UI offer a retry instead of showing a broken download.
  bytes        bigint CHECK (bytes IS NULL OR bytes >= 0),
  PRIMARY KEY (user_id, video_id)
);

CREATE INDEX downloads_user_idx ON downloads (user_id, requested_at DESC);

-- ADR 0003: offline works only for content Loupe owns. Class B is referenced
-- rather than stored, so there is nothing to cache and no right to cache it.
--
-- Enforced here for the same reason the Class A/B capability asymmetry is
-- enforced in 0002: a rule that lives only in a code path holds until somebody
-- writes a second code path.
CREATE FUNCTION reject_referenced_download() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM videos
    WHERE id = NEW.video_id AND source_class = 'referenced'
  ) THEN
    RAISE EXCEPTION 'referenced content cannot be downloaded (ADR 0003)';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER downloads_owned_only
  BEFORE INSERT OR UPDATE ON downloads
  FOR EACH ROW EXECUTE FUNCTION reject_referenced_download();
