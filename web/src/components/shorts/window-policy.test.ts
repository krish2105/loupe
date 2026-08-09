import { describe, expect, it } from "vitest";
import {
  DESTROY_BEYOND,
  activeIndexFromScroll,
  MAX_CONCURRENT_LOADS,
  PRELOAD_AHEAD,
  concurrentLoads,
  planWindow,
  slotsToDestroy,
} from "./window-policy";

/**
 * §13's warning, made testable: "Get this wrong and five video elements will
 * fight for bandwidth."
 *
 * Too many elements loading at once presents as stutter on a slow device —
 * the hardest symptom to trace back to its cause. Asserting the policy
 * directly answers the bandwidth question before any device is involved, which
 * matters because the Phase 8 gate needs hardware this project does not have.
 */

const FEED = 20;

describe("planWindow", () => {
  it("plays exactly one item", () => {
    for (let active = 0; active < FEED; active++) {
      const playing = planWindow(active, FEED).filter((slot) => slot.playing);
      expect(playing).toHaveLength(1);
      expect(playing[0]!.index).toBe(active);
    }
  });

  it("never has more than three elements loading", () => {
    // The number §13 is warning about.
    for (let active = 0; active < FEED; active++) {
      expect(concurrentLoads(planWindow(active, FEED))).toBeLessThanOrEqual(
        MAX_CONCURRENT_LOADS,
      );
    }
    expect(MAX_CONCURRENT_LOADS).toBe(3);
  });

  it("preloads the next two and no further", () => {
    const plans = planWindow(10, FEED);

    expect(plans[11]!.preload).toBe("auto");
    expect(plans[12]!.preload).toBe("auto");
    expect(plans[13]!.preload).toBe("none");
  });

  it("does not re-fetch items behind the active one", () => {
    const plans = planWindow(10, FEED);

    // They keep their buffer while mounted; fetching again would compete with
    // the items ahead for the bandwidth this policy exists to protect.
    expect(plans[9]!.preload).toBe("none");
    expect(plans[8]!.preload).toBe("none");
  });

  it("destroys beyond ±3", () => {
    const plans = planWindow(10, FEED);

    expect(plans[7]!.mounted).toBe(true);
    expect(plans[6]!.mounted).toBe(false);
    expect(plans[13]!.mounted).toBe(true);
    expect(plans[14]!.mounted).toBe(false);
  });

  it("mounts at most seven elements", () => {
    for (let active = 0; active < FEED; active++) {
      const mounted = planWindow(active, FEED).filter((slot) => slot.mounted);
      expect(mounted.length).toBeLessThanOrEqual(DESTROY_BEYOND * 2 + 1);
    }
  });

  it("clamps at the start of the feed", () => {
    const plans = planWindow(0, FEED);

    expect(plans[0]!.playing).toBe(true);
    expect(plans.filter((slot) => slot.mounted).map((s) => s.index)).toEqual([
      0, 1, 2, 3,
    ]);
  });

  it("clamps at the end of the feed", () => {
    const plans = planWindow(FEED - 1, FEED);

    expect(plans[FEED - 1]!.playing).toBe(true);
    // Nothing ahead to preload, so only the active item loads.
    expect(concurrentLoads(plans)).toBe(1);
  });

  it("handles a feed of one", () => {
    const plans = planWindow(0, 1);

    expect(plans).toHaveLength(1);
    expect(plans[0]!.playing).toBe(true);
    expect(concurrentLoads(plans)).toBe(1);
  });

  it("handles an empty feed", () => {
    expect(planWindow(0, 0)).toEqual([]);
  });

  it("honours the documented constants", () => {
    expect(DESTROY_BEYOND).toBe(3);
    expect(PRELOAD_AHEAD).toBe(2);
  });
});

describe("slotsToDestroy", () => {
  it("names what leaves the window when scrolling forward", () => {
    // Moving 10 -> 11 drops index 7.
    expect(slotsToDestroy(10, 11, FEED)).toEqual([7]);
  });

  it("names what leaves the window when scrolling back", () => {
    expect(slotsToDestroy(10, 9, FEED)).toEqual([13]);
  });

  it("drops everything when jumping far", () => {
    // A jump beyond the window means the whole previous set goes.
    expect(slotsToDestroy(0, 15, FEED)).toEqual([0, 1, 2, 3]);
  });

  it("drops nothing when the active item has not changed", () => {
    expect(slotsToDestroy(5, 5, FEED)).toEqual([]);
  });

  it("drops the trailing slot when moving back toward the start", () => {
    // Moving 1 -> 0 narrows the forward edge from 4 to 3.
    expect(slotsToDestroy(1, 0, FEED)).toEqual([4]);
  });
});

describe("activeIndexFromScroll", () => {
  const SLOT = 800;

  it("is zero at the top", () => {
    expect(activeIndexFromScroll(0, SLOT, 10)).toBe(0);
  });

  it("rounds to the nearest slot", () => {
    // Snapping guarantees alignment at rest; rounding handles mid-scroll.
    expect(activeIndexFromScroll(SLOT * 3, SLOT, 10)).toBe(3);
    expect(activeIndexFromScroll(SLOT * 3 + 100, SLOT, 10)).toBe(3);
    expect(activeIndexFromScroll(SLOT * 3 + 500, SLOT, 10)).toBe(4);
  });

  it("clamps past the end", () => {
    expect(activeIndexFromScroll(SLOT * 999, SLOT, 10)).toBe(9);
  });

  it("clamps below zero", () => {
    // Rubber-banding produces negative scrollTop on iOS.
    expect(activeIndexFromScroll(-300, SLOT, 10)).toBe(0);
  });

  it("survives a zero-height container", () => {
    // Before layout, clientHeight is 0. Dividing by it would be Infinity.
    expect(activeIndexFromScroll(500, 0, 10)).toBe(0);
  });

  it("survives an empty feed", () => {
    expect(activeIndexFromScroll(0, SLOT, 0)).toBe(0);
  });
});
