"use client";

import { useEffect, useRef } from "react";
import { usePlayerControls, usePlayerStore } from "@/components/player/PlayerContext";
import { ProgressReporter } from "@/components/player/progress-reporter";
import { resumePosition } from "@/components/player/resume-policy";
import type { QueueStore } from "./queue-store";

/**
 * Keeps the playhead across a reload, and across switching episodes and back.
 *
 * The queue already survived a reload; the position did not, so returning to a
 * forty-minute episode meant scrubbing for the place you had reached. This is
 * the smaller half of the §9.1 resume story: the API's `/resume` endpoint
 * answers "where is this signed-in person, on any device" and needs a round
 * trip, and this answers "where was this tab", instantly and without an
 * account.
 *
 * Positions are per episode rather than one global playhead, which falls out of
 * the storage shape and is what makes switching to something else and coming
 * back work at all.
 */
export function usePlayhead(store: QueueStore, videoId: string | null) {
  const player = usePlayerStore();
  const { seek } = usePlayerControls();

  // ProgressReporter already decides when a position is worth writing — every
  // ten seconds, immediately after a seek, never the same second twice. Reusing
  // it rather than writing a second throttle keeps one answer to that question.
  const reporterRef = useRef(new ProgressReporter(10));

  // Which episode has already been restored. Without it, every state change
  // while playing would seek back to the saved position, which is a player that
  // refuses to move.
  const restoredRef = useRef<string | null>(null);

  useEffect(() => {
    if (!videoId) return;

    const reporter = reporterRef.current;
    reporter.reset();

    const save = () => {
      const { currentTime } = player.getSnapshot();
      if (!reporter.shouldReport(currentTime, "tick")) return;
      reporter.markReported(currentTime);
      store.rememberPosition(videoId, currentTime);
    };

    const unsubscribe = player.subscribe(() => {
      const { isReady, duration } = player.getSnapshot();

      // Restore once, and only once the media knows its length, because the
      // "effectively finished" test needs a duration to compare against. The
      // store holds a seek requested before metadata (§5.1), so waiting here
      // costs nothing but makes the decision correct.
      if (isReady && restoredRef.current !== videoId) {
        restoredRef.current = videoId;

        const target = resumePosition(store.positionFor(videoId), duration);
        if (target !== null) {
          seek(target);
          // Marked as already reported so the restore itself is not written
          // straight back, which would otherwise be the first thing that
          // happens on every load.
          reporter.markReported(target);
        }
        return;
      }

      save();
    });

    // An episode that finished has nowhere useful to resume to, and leaving the
    // position at the end would make replaying it start on the credits.
    const unsubscribeEnded = player.onEnded(() => store.forgetPosition(videoId));

    // A tab closed between ticks would otherwise lose up to ten seconds, which
    // is exactly the case this whole hook exists for.
    const onHide = () => {
      const { currentTime } = player.getSnapshot();
      if (currentTime > 0) store.rememberPosition(videoId, currentTime);
    };

    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onHide);

    return () => {
      onHide();
      unsubscribe();
      unsubscribeEnded();
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onHide);
    };
  }, [player, store, videoId, seek]);
}
