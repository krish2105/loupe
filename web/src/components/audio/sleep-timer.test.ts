import { describe, expect, it } from "vitest";
import {
  deadlineFor,
  formatCountdown,
  msUntilNextTick,
  remainingSeconds,
} from "./sleep-timer";

/**
 * Sleep timer arithmetic (ADR 0003).
 *
 * The interesting cases are all about a tab that was not awake. A sleep timer
 * runs almost entirely in a backgrounded tab, where timers fire late, rarely,
 * or not at all until the tab is looked at again.
 */

const NOW = 1_700_000_000_000;

describe("remaining time", () => {
  it("is computed from the deadline, not counted down", () => {
    /**
     * The whole design. Background tabs throttle intervals to roughly one a
     * minute, so a decrementing timer set for fifteen minutes would still read
     * eleven after twenty. Recomputing is correct however few ticks ran.
     */
    const deadline = deadlineFor(15, NOW);

    // Twenty minutes later, having ticked perhaps twice.
    expect(remainingSeconds(deadline, NOW + 20 * 60_000)).toBe(0);
  });

  it("counts down as time passes", () => {
    const deadline = deadlineFor(30, NOW);

    expect(remainingSeconds(deadline, NOW)).toBe(1800);
    expect(remainingSeconds(deadline, NOW + 90_000)).toBe(1710);
  });

  it("floors at zero rather than going negative", () => {
    const deadline = deadlineFor(1, NOW);

    expect(remainingSeconds(deadline, NOW + 10 * 60_000)).toBe(0);
  });
});

describe("the countdown display", () => {
  it("always shows seconds", () => {
    // "14 min" for sixty seconds before jumping to "13 min" gives no sign the
    // timer is running, which is the one thing a countdown is for.
    expect(formatCountdown(14 * 60 + 37)).toBe("14:37");
  });

  it("pads seconds so the width does not jump", () => {
    expect(formatCountdown(65)).toBe("1:05");
    expect(formatCountdown(60)).toBe("1:00");
  });

  it("shows hours only when there are hours", () => {
    expect(formatCountdown(3600)).toBe("1:00:00");
    expect(formatCountdown(3599)).toBe("59:59");
  });

  it("reads zero rather than empty at the end", () => {
    expect(formatCountdown(0)).toBe("0:00");
  });

  it("does not render a negative clock", () => {
    expect(formatCountdown(-5)).toBe("0:00");
  });
});

describe("tick alignment", () => {
  it("waits until the displayed second actually changes", () => {
    /**
     * A flat 1000ms interval drifts a few milliseconds a tick and eventually
     * skips a number, which reads as a stutter in something whose only job is
     * to count smoothly.
     */
    const deadline = NOW + 30_400;

    expect(msUntilNextTick(deadline, NOW)).toBe(400);
  });

  it("waits a full second when it lands exactly on one", () => {
    expect(msUntilNextTick(NOW + 30_000, NOW)).toBe(1000);
  });

  it("never returns something small enough to spin", () => {
    expect(msUntilNextTick(NOW + 30_010, NOW)).toBeGreaterThanOrEqual(50);
  });

  it("returns zero once the deadline has passed", () => {
    expect(msUntilNextTick(NOW - 1, NOW)).toBe(0);
  });
});
