-- 0010 — where each playlist item starts, and why it is there
-- Plan ref: §11 AI playlists.
--
-- The playlist rationale explains the ordering of the list. These two columns
-- explain the individual item: the moment in the talk that matched the brief,
-- and the sentence the transcript says there.
--
-- Without them the feature degrades into a saved search — a list of titles that
-- happen to be related, which is exactly what a platform without a transcript
-- layer would produce. The point of building on transcripts is being able to
-- say "start at 14:20, that is where she answers this".
--
-- Nullable, because a hand-made playlist has neither and inventing a start
-- position for one would be a lie the UI would then render.
ALTER TABLE playlist_items
  ADD COLUMN start_sec integer CHECK (start_sec IS NULL OR start_sec >= 0),
  ADD COLUMN note      text;
