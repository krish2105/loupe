/**
 * The sleep timer's arithmetic (ADR 0003).
 *
 * Its own module for the reason every other rule in audio mode is: the wrong
 * version of this is a subtraction inside a component, and the ways it goes
 * wrong are invisible in a five-minute test and obvious after an hour.
 *
 * The decision underneath all of it: remaining time is **computed from a
 * deadline**, never decremented.
 *
 * Decrementing looks equivalent and is not. `setInterval` is throttled to about
 * once a minute in a background tab, which is exactly where a sleep timer
 * spends its life, and every skipped tick is a minute the countdown never
 * subtracts. A timer set for fifteen minutes would still read eleven after
 * twenty. Recomputing from a deadline is correct however few times it runs.
 */

export const SLEEP_OPTIONS = [15, 30, 45, 60] as const;

/** Seconds left, floored at zero. */
export function remainingSeconds(deadlineMs: number, nowMs: number): number {
  return Math.max(0, Math.round((deadlineMs - nowMs) / 1000));
}

export function deadlineFor(minutes: number, nowMs: number): number {
  return nowMs + minutes * 60_000;
}

/**
 * `m:ss` under an hour, `h:mm:ss` over it.
 *
 * Seconds are always shown. A countdown that reads "14 min" for sixty seconds
 * before jumping to "13 min" gives no sign it is running, which is the one
 * thing a countdown exists to do.
 */
export function formatCountdown(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));

  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;

  const pad = (value: number) => String(value).padStart(2, "0");

  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(secs)}`
    : `${minutes}:${pad(secs)}`;
}

/**
 * How long to wait before the next tick.
 *
 * Aligned to the next whole second rather than a flat 1000ms, so the displayed
 * number changes when the second actually changes. A flat interval drifts a few
 * milliseconds per tick and eventually skips a number, which reads as a stutter
 * in something whose only job is to count down smoothly.
 *
 * Clamped to at least 50ms so a mistimed call cannot spin.
 */
export function msUntilNextTick(deadlineMs: number, nowMs: number): number {
  const untilDeadline = deadlineMs - nowMs;
  if (untilDeadline <= 0) return 0;

  const intoSecond = untilDeadline % 1000;
  return Math.max(50, intoSecond === 0 ? 1000 : intoSecond);
}
