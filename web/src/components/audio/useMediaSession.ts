"use client";

import { useEffect } from "react";
import { usePlayerControls, usePlayerStore } from "@/components/player/PlayerContext";
import { useQueueControls, useQueueState } from "./QueueContext";

/**
 * OS media controls (ADR 0003).
 *
 * Puts the episode on the lock screen and wires hardware media keys, the
 * headphone button, and the notification-shade controls to the queue. Without
 * it, pressing pause on a pair of headphones does nothing, which is the point
 * at which a web audio player stops feeling like an audio player.
 *
 * Deliberately narrow: this reports state and registers handlers. It owns no
 * playback logic, so there is no second copy of "what does next mean" for the
 * in-page buttons and the lock screen to disagree about.
 *
 * ADR 0003 already recorded what this cannot fix. On iOS, Safari suspends web
 * audio aggressively once the browser is backgrounded, and Media Session
 * changes none of that — it delivers the controls and the metadata, not the
 * background execution. §3.2 rules out a native app, so a PWA is the ceiling.
 */
export function useMediaSession() {
  const { current } = useQueueState();
  const { next, previous } = useQueueControls();
  const { play, pause, seek, nudge } = usePlayerControls();
  const store = usePlayerStore();

  useEffect(() => {
    if (typeof navigator === "undefined" || !("mediaSession" in navigator)) return;

    const session = navigator.mediaSession;

    if (!current) {
      session.metadata = null;
      session.playbackState = "none";
      return;
    }

    session.metadata = new MediaMetadata({
      title: current.title,
      artist: current.channelName,
      album: "Loupe",
    });

    const handlers: [MediaSessionAction, MediaSessionActionHandler][] = [
      ["play", () => void play()],
      ["pause", () => pause()],
      ["previoustrack", () => previous()],
      ["nexttrack", () => next()],
      // Matched to the in-page buttons rather than to the platform defaults, so
      // the lock screen and the page skip by the same amount.
      ["seekbackward", () => nudge(-15)],
      ["seekforward", () => nudge(30)],
      ["seekto", (details) => {
        if (details.seekTime !== undefined && details.seekTime !== null) {
          seek(details.seekTime);
        }
      }],
    ];

    for (const [action, handler] of handlers) {
      try {
        session.setActionHandler(action, handler);
      } catch {
        // Browsers reject actions they do not implement. An unsupported action
        // should cost that one control, not every control after it.
      }
    }

    return () => {
      for (const [action] of handlers) {
        try {
          session.setActionHandler(action, null);
        } catch {
          // Same reason.
        }
      }
    };
  }, [current, play, pause, next, previous, seek, nudge]);

  // Playback state and position are pushed from the store rather than from
  // React state, so the lock screen's scrubber tracks the audio instead of
  // tracking renders.
  useEffect(() => {
    if (typeof navigator === "undefined" || !("mediaSession" in navigator)) return;

    return store.subscribe(() => {
      const snapshot = store.getSnapshot();
      navigator.mediaSession.playbackState = snapshot.isPlaying
        ? "playing"
        : "paused";

      if (!snapshot.isReady || !Number.isFinite(snapshot.duration)) return;

      try {
        navigator.mediaSession.setPositionState({
          duration: snapshot.duration,
          position: Math.min(snapshot.currentTime, snapshot.duration),
          playbackRate: 1,
        });
      } catch {
        // Throws when position exceeds duration, which happens briefly at the
        // end of a track. Not worth a guard clause per browser quirk.
      }
    });
  }, [store]);
}
