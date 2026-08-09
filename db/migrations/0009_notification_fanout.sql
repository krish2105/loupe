-- 0009 — notification fan-out
-- Plan ref: §6.2 ("fan-out on write"), §5.1 (idempotency), Phase 10 deliverable.
--
-- Fan-out lives in the database rather than in a service because three
-- different services write the rows that should produce a notification: the
-- pipeline flips a Class A video to transcoded, the ingest worker inserts Class
-- B rows nightly, and the core API writes comment replies. Putting the fan-out
-- in one of them means the other two silently produce nothing, and the symptom
-- is an empty notifications page that looks like a UI bug.
--
-- The honest limit: this is a synchronous insert of one row per subscriber
-- inside the publishing transaction. At a few hundred subscribers per channel
-- that is a millisecond and the simplicity is worth it. At a hundred thousand
-- it is a long-running transaction holding locks, and the fan-out has to move
-- behind the queue in §14 — read on write for large channels, fan-out on write
-- for small ones. That crossover is the standard one and this is deliberately
-- on the small side of it.

-- §5.1: idempotent. A video can reach a watchable state more than once — a
-- transcode retried after a failure re-enters 'transcoded', and the ingest
-- worker re-inserts nothing but does update rows nightly. Without this a
-- subscriber is told about the same talk twice, which is the specific way
-- notification systems lose trust.
CREATE UNIQUE INDEX notifications_new_upload_once
  ON notifications (user_id, target_id)
  WHERE kind = 'new_upload';

-- Whether a video can actually be watched right now.
--
-- Class B is watchable the moment it exists — it plays on the source platform
-- and never enters the pipeline (§4).
--
-- Class A becomes watchable at 'transcoded'. The comparison relies on enum
-- declaration order in 0001, which puts every later stage above it, and that
-- includes 'failed_transcribing' and 'failed_embedding'. That is intended
-- rather than tolerated: a talk whose transcript failed still plays, so its
-- subscribers should still hear about it. What they lose is the intelligence
-- layer, not the video.
CREATE FUNCTION video_is_watchable(
  p_class  source_class,
  p_status processing_status
) RETURNS boolean
IMMUTABLE PARALLEL SAFE LANGUAGE sql AS $$
  SELECT CASE
    WHEN p_class = 'referenced' THEN p_status = 'referenced_only'
    ELSE p_status >= 'transcoded'
  END;
$$;

CREATE FUNCTION fan_out_new_upload() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  -- Only when the video crosses into being watchable and public. An UPDATE that
  -- edits a title on an already-published video must not re-notify.
  IF NOT (NEW.visibility = 'public'
          AND video_is_watchable(NEW.source_class, NEW.processing_status)) THEN
    RETURN NEW;
  END IF;

  IF TG_OP = 'UPDATE'
     AND OLD.visibility = 'public'
     AND video_is_watchable(OLD.source_class, OLD.processing_status) THEN
    RETURN NEW;
  END IF;

  INSERT INTO notifications (user_id, kind, target_id)
  SELECT s.user_id, 'new_upload', NEW.id
  FROM subscriptions s
  WHERE s.channel_id = NEW.channel_id
    AND s.notify_enabled
    -- You hear about talks posted after you followed, not the back catalogue.
    --
    -- This is the semantics a viewer expects, and it also happens to be what
    -- stops the Class B backfill from generating a notification per subscriber
    -- per historical video the first time a channel is ingested. Getting the
    -- semantics right removed the need for a special case; a published_at
    -- recency window would have been the wrong fix for the right symptom.
    AND NEW.published_at IS NOT NULL
    AND NEW.published_at > s.created_at
  ON CONFLICT DO NOTHING;

  RETURN NEW;
END;
$$;

CREATE TRIGGER videos_fan_out_new_upload
  AFTER INSERT OR UPDATE OF visibility, processing_status ON videos
  FOR EACH ROW EXECUTE FUNCTION fan_out_new_upload();

-- Replies. One level only (§6.2), so the recipient is always the parent
-- comment's author and there is no thread to walk.
CREATE FUNCTION fan_out_reply() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  parent_author uuid;
BEGIN
  IF NEW.parent_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT user_id INTO parent_author FROM comments WHERE id = NEW.parent_id;

  -- Replying to yourself is not news.
  IF parent_author IS NULL OR parent_author = NEW.user_id THEN
    RETURN NEW;
  END IF;

  -- target_id is the video, not the comment: there is no comment permalink to
  -- send anyone to, and a notification that opens the talk the conversation is
  -- on is more useful than one that opens nothing.
  INSERT INTO notifications (user_id, kind, actor_id, target_id)
  VALUES (parent_author, 'reply', NEW.user_id, NEW.video_id);

  RETURN NEW;
END;
$$;

CREATE TRIGGER comments_fan_out_reply
  AFTER INSERT ON comments
  FOR EACH ROW EXECUTE FUNCTION fan_out_reply();

-- notifications.target_id is polymorphic — a video today, plausibly a comment
-- or a channel later — so it cannot carry a foreign key and gets no cascade.
-- Without this, deleting a video leaves rows that render as "posted (nothing)"
-- and keep counting toward the unread badge forever. Both current kinds target
-- a video, so one trigger covers them.
CREATE FUNCTION purge_notifications_for_video() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  DELETE FROM notifications WHERE target_id = OLD.id;
  RETURN OLD;
END;
$$;

CREATE TRIGGER videos_purge_notifications
  BEFORE DELETE ON videos
  FOR EACH ROW EXECUTE FUNCTION purge_notifications_for_video();
