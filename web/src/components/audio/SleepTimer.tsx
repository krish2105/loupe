"use client";

import { useEffect, useState } from "react";
import { usePlayerControls } from "@/components/player/PlayerContext";
import {
  SLEEP_OPTIONS,
  deadlineFor,
  formatCountdown,
  msUntilNextTick,
  remainingSeconds,
} from "./sleep-timer";
import { cn } from "@/lib/utils";

/**
 * The sleep timer, with a countdown (ADR 0003).
 *
 * Its own component so the per-second tick re-renders eleven characters rather
 * than the whole player bar. The bar already re-renders on every `timeupdate`,
 * so this is not a large saving in practice — but the transport controls have
 * no business re-rendering because a clock moved, and keeping that true is
 * cheaper than deciding later which of two reasons caused a render.
 *
 * The timer holds a deadline and derives the display from it. See
 * sleep-timer.ts for why that is not the same as counting down.
 *
 * It pauses rather than stops, so the position survives and the playhead
 * persistence picks it up. Someone who fell asleep wants to resume the episode,
 * not restart it.
 */
export function SleepTimer() {
  const { pause } = usePlayerControls();

  const [deadline, setDeadline] = useState<number | null>(null);
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (deadline === null) return;

    let timer: number;

    const tick = () => {
      const left = remainingSeconds(deadline, Date.now());
      setRemaining(left);

      if (left <= 0) {
        pause();
        setDeadline(null);
        return;
      }

      timer = window.setTimeout(tick, msUntilNextTick(deadline, Date.now()));
    };

    // Scheduled rather than called, so nothing sets state synchronously inside
    // the effect. The first tick lands within a second either way.
    timer = window.setTimeout(tick, msUntilNextTick(deadline, Date.now()));

    // A backgrounded tab throttles timers to roughly one a minute, so the
    // deadline can pass long before the next tick. Checking on the way back
    // means the audio has stopped by the time anyone looks, rather than playing
    // on until a late timer notices.
    const onVisible = () => {
      if (document.visibilityState === "visible") tick();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [deadline, pause]);

  if (deadline === null) {
    return (
      <>
        <label className="sr-only" htmlFor="mini-sleep">
          Sleep timer
        </label>
        <select
          id="mini-sleep"
          value=""
          onChange={(event) => {
            const minutes = Number(event.target.value);
            if (!minutes) return;
            setDeadline(deadlineFor(minutes, Date.now()));
            setRemaining(minutes * 60);
          }}
          className={cn(
            "rounded-(--radius-sm) border border-rule bg-canvas px-2 py-1",
            "text-(length:--step--2) text-muted",
          )}
        >
          <option value="">Sleep</option>
          {SLEEP_OPTIONS.map((minutes) => (
            <option key={minutes} value={minutes}>
              {minutes} min
            </option>
          ))}
        </select>
      </>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setDeadline(null)}
      title={`Stopping in ${formatCountdown(remaining)}. Cancel the sleep timer.`}
      className={cn(
        "flex items-center gap-1.5 rounded-(--radius-sm) border border-brand",
        "px-2 py-1 text-(length:--step--2) text-brand transition-colors",
        "hover:bg-brand-faint",
      )}
    >
      {/* Announced politely so a screen reader is not interrupted every second,
          and tabular figures so eleven characters do not shift the bar around
          as the digits change. */}
      <span aria-live="polite" className="font-mono tabular-nums">
        {formatCountdown(remaining)}
      </span>
      <span aria-hidden="true">×</span>
      <span className="sr-only">Cancel the sleep timer</span>
    </button>
  );
}
