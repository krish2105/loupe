"use client";

import { useEffect, useRef } from "react";
import { usePlayerStore } from "./PlayerContext";
import { ProgressReporter } from "./progress-reporter";
import { createClient } from "@/lib/supabase/client";
import { API_URL } from "@/lib/api";

/**
 * Persists playback position (§9.1).
 *
 * Subscribes to the store imperatively rather than through usePlayerState, so
 * a write every ten seconds costs zero renders.
 *
 * Fire-and-forget in the literal sense: nothing awaits the response and a
 * failure is swallowed. Losing a position write is a minor inconvenience;
 * showing someone an error because their history did not save is worse than
 * the thing it reports.
 */
export function useProgressReporting(videoId: string | null) {
  const store = usePlayerStore();
  const reporterRef = useRef(new ProgressReporter(10));

  useEffect(() => {
    // Signed-out visitors have no history, and there is nowhere to send it
    // without an API. Both are ordinary states, not errors.
    if (!videoId || !API_URL) return;

    const supabase = createClient();
    if (!supabase) return;

    const reporter = reporterRef.current;
    reporter.reset();

    let token: string | null = null;
    let disposed = false;

    void supabase.auth.getSession().then(({ data }) => {
      if (!disposed) token = data.session?.access_token ?? null;
    });

    function send(positionSec: number, watchPct: number, completed: boolean) {
      if (!token) return;

      // fetch with keepalive rather than sendBeacon: a beacon cannot carry an
      // Authorization header, and the endpoint requires a verified token.
      // keepalive survives the document being torn down, which is the only
      // property sendBeacon was wanted for.
      void fetch(`${API_URL}/v1/watch-events`, {
        method: "POST",
        keepalive: true,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          video_id: videoId,
          position_sec: Math.floor(positionSec),
          watch_pct: watchPct,
          completed,
        }),
      }).catch(() => {
        // Deliberately silent. See the note above.
      });
    }

    function report(reason: "tick" | "pause" | "unload") {
      const { currentTime, duration } = store.getSnapshot();
      if (!reporter.shouldReport(currentTime, reason)) return;

      const watchPct = duration > 0 ? Math.min(1, currentTime / duration) : 0;
      reporter.markReported(currentTime);
      send(currentTime, watchPct, watchPct >= 0.95);
    }

    const unsubscribe = store.subscribe(() => report("tick"));

    const onHide = () => report("unload");
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") onHide();
    };

    // pagehide fires on mobile Safari, where unload does not. visibilitychange
    // covers the app being backgrounded without the page ever unloading.
    window.addEventListener("pagehide", onHide);
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      disposed = true;
      report("pause");
      unsubscribe();
      window.removeEventListener("pagehide", onHide);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [store, videoId]);
}
