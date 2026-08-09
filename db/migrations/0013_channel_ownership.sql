-- 0013 — who owns a channel
--
-- The schema has never said. Until now the only link between a user and a
-- channel was `subscriptions`, which records interest, not authorship — so
-- there was no answer to "which channel does this person upload into", and the
-- upload page could not be finished. It generated a random video id, which
-- could never satisfy the foreign key on `videos`, and the whole flow died
-- there. That was not an oversight in the page; it was a gap in the model.
--
-- Class B channels stay ownerless. They are synthetic records standing in for
-- someone else's YouTube channel (§6.1) and nobody on this platform authored
-- them, so `owner_id` is nullable rather than defaulted — and the constraint
-- below makes claiming one impossible rather than merely unusual.
--
-- One channel per person, enforced by a partial unique index. That is a
-- product decision, not a technical limit: it is the smallest thing that works
-- and what most platforms do before they have a studio worth managing several
-- from. Wanting several later means dropping one index, which is why the rule
-- lives in an index rather than being spread through the code that would have
-- to assume it.

ALTER TABLE channels
  ADD COLUMN owner_id uuid REFERENCES users(id) ON DELETE CASCADE;

-- A referenced channel is not a person's. Enforced rather than remembered,
-- matching how §4's capability asymmetry is handled on `videos`.
ALTER TABLE channels
  ADD CONSTRAINT channels_referenced_never_owned
    CHECK (source_class <> 'referenced' OR owner_id IS NULL);

CREATE UNIQUE INDEX channels_one_per_owner
  ON channels (owner_id)
  WHERE owner_id IS NOT NULL;

-- Finding a person's channel happens on every upload and every studio page.
COMMENT ON COLUMN channels.owner_id IS
  'The user who authored this channel. NULL for referenced (Class B) channels, '
  'which stand in for upstream channels nobody here owns.';
