/**
 * Which transcript line is highlighted (ADR 0003).
 *
 * Its own module for the same reason the queue and shorts-window rules are:
 * the rule is small, wrong in a way nobody notices until they read along and
 * the highlight sits one line ahead, and testable without a component.
 */

export type TimedLine = { start_sec: number };

/**
 * The last line that has started, rather than the one whose span contains the
 * playhead.
 *
 * The two differ during a gap — a pause, or a stretch the ASR produced no words
 * for — and highlighting nothing through every pause makes the transcript look
 * broken.
 */
export function activeLine(lines: TimedLine[], seconds: number): number {
  let active = -1;

  for (let index = 0; index < lines.length; index++) {
    if (lines[index]!.start_sec <= seconds) active = index;
    else break;
  }

  return active;
}
