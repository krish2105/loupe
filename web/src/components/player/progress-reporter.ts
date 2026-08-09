/**
 * Decides when a playback position is worth persisting (§9.1).
 *
 * "Write position every 10s and on pause/unload. Debounced, fire-and-forget."
 * The decision is pure and separate from the sending, because the failure this
 * guards against is invisible: a reporter that fires on every timeupdate would
 * write four rows a second per viewer into an append-only table, and nothing
 * about the UI would look wrong while it happened.
 */

export type ReportReason = "tick" | "pause" | "unload";

export class ProgressReporter {
  private lastReportedSec: number | null = null;

  constructor(private readonly intervalSec = 10) {}

  shouldReport(positionSec: number, reason: ReportReason): boolean {
    const position = Math.floor(positionSec);

    // Position zero carries no information — there is nothing to resume to.
    if (position <= 0) return false;

    // Never write the same second twice, whatever the reason. Pause and unload
    // often fire together as a tab closes.
    if (position === this.lastReportedSec) return false;

    if (reason !== "tick") return true;

    // A seek counts: the distance test is on position, not elapsed real time,
    // so jumping to a citation records the new place immediately rather than
    // waiting out the interval.
    return this.lastReportedSec === null
      ? position >= this.intervalSec
      : Math.abs(position - this.lastReportedSec) >= this.intervalSec;
  }

  markReported(positionSec: number): void {
    this.lastReportedSec = Math.floor(positionSec);
  }

  /** Test seam and a reset for when the player moves to another talk. */
  reset(): void {
    this.lastReportedSec = null;
  }
}
