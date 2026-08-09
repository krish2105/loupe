-- 0007 — make append-only survivable
--
-- 0001 blocked every UPDATE and DELETE on watch_events. That is right for the
-- application and wrong for everything else: a row-level DELETE trigger also
-- fires on a *cascading* delete, so `DELETE FROM users` and `DELETE FROM
-- videos` both became impossible the moment any history existed.
--
-- Account deletion is not an optional feature, so this needs an escape hatch —
-- but one that ordinary application code cannot reach by accident. A
-- transaction-scoped setting does that: a purge has to say so explicitly, and
-- the setting dies with the transaction.
--
-- UPDATE stays unconditionally blocked. §6.5 is about history never being
-- rewritten; deleting a person's data on request is a different act.

CREATE OR REPLACE FUNCTION reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE'
     AND current_setting('loupe.allow_purge', true) = 'on'
  THEN
    RETURN OLD;
  END IF;

  RAISE EXCEPTION
    '% is append-only (plan §6.5); % rejected. For an authorised purge, SET LOCAL loupe.allow_purge = ''on''.',
    TG_TABLE_NAME, TG_OP;
END;
$$;
