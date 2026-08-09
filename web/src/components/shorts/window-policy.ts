/**
 * Which shorts are mounted, which are loading, and which one plays — §13.
 *
 *     "A vertical feed feels broken unless the next item is already buffered.
 *      Use CSS scroll-snap for the track, an intersection observer for
 *      play/pause, preload manifests for index +1 and +2, and destroy players
 *      beyond ±3. Get this wrong and five video elements will fight for
 *      bandwidth."
 *
 * That last sentence is why this is a pure function with its own tests rather
 * than conditions scattered through a component. Too many elements loading at
 * once is a *logic* bug that presents as a *performance* bug — it looks like
 * stutter on a slow device, which is the hardest kind of symptom to trace back
 * to its cause, and §15 already rates shorts performance on mid-range hardware
 * as a high-likelihood risk.
 *
 * Testing the policy directly means the bandwidth question is answered before
 * a device is ever involved.
 */

/** Beyond this distance the video element is removed entirely. */
export const DESTROY_BEYOND = 3;

/** How many items ahead get their manifest fetched. */
export const PRELOAD_AHEAD = 2;

/**
 * The most elements that may be fetching at once: the active one plus the two
 * ahead of it. Named because it is the number §13 is warning about.
 */
export const MAX_CONCURRENT_LOADS = PRELOAD_AHEAD + 1;

export type PreloadHint = "none" | "metadata" | "auto";

export type SlotPlan = {
  index: number;
  /** Whether a <video> element exists for this slot at all. */
  mounted: boolean;
  preload: PreloadHint;
  playing: boolean;
};

export function planWindow(
  activeIndex: number,
  total: number,
  options: { destroyBeyond?: number; preloadAhead?: number } = {},
): SlotPlan[] {
  const destroyBeyond = options.destroyBeyond ?? DESTROY_BEYOND;
  const preloadAhead = options.preloadAhead ?? PRELOAD_AHEAD;

  const plans: SlotPlan[] = [];

  for (let index = 0; index < total; index++) {
    const distance = index - activeIndex;
    const mounted = Math.abs(distance) <= destroyBeyond;

    // Only forward: an item already behind has its buffer if it is still
    // mounted, and re-fetching it would compete with the items ahead for
    // exactly the bandwidth §13 is protecting.
    const shouldLoad = mounted && distance >= 0 && distance <= preloadAhead;

    plans.push({
      index,
      mounted,
      preload: shouldLoad ? "auto" : "none",
      playing: index === activeIndex,
    });
  }

  return plans;
}

/**
 * Slots that were mounted and no longer should be.
 *
 * Returned rather than inferred by the component, because "destroy beyond ±3"
 * is only true if something actually destroys them. A React key change unmounts
 * the element; this is what tells the caller which keys to drop.
 */
export function slotsToDestroy(
  previousActive: number,
  nextActive: number,
  total: number,
  destroyBeyond: number = DESTROY_BEYOND,
): number[] {
  const wasMounted = new Set(
    planWindow(previousActive, total, { destroyBeyond })
      .filter((slot) => slot.mounted)
      .map((slot) => slot.index),
  );

  const stillMounted = new Set(
    planWindow(nextActive, total, { destroyBeyond })
      .filter((slot) => slot.mounted)
      .map((slot) => slot.index),
  );

  return [...wasMounted].filter((index) => !stillMounted.has(index)).sort((a, b) => a - b);
}

/**
 * The invariant §13 is really asking for, checkable at runtime.
 *
 * Exported so a development build can assert it rather than trusting that the
 * component still honours the policy after someone edits it.
 */
export function concurrentLoads(plans: SlotPlan[]): number {
  return plans.filter((slot) => slot.mounted && slot.preload === "auto").length;
}

/**
 * Which slot is active, from the scroll position.
 *
 * §13 specifies an intersection observer, and this is a deliberate deviation.
 * IntersectionObserver never fires in the browser used to verify this build —
 * not even with the default root observing document.body, which must always
 * produce an initial callback — so the observer version could not be tested at
 * all. An untestable mechanism is worse than a marginally more expensive one,
 * particularly for a surface whose gate is a performance claim.
 *
 * On a snap container the arithmetic is exact rather than approximate: every
 * slot is the same height and snapping guarantees alignment at rest. That
 * makes it a pure function, which is the other reason to prefer it.
 *
 * Cost is one rounding per animation frame while scrolling. The observer's
 * advantage is real but small at this element count.
 */
export function activeIndexFromScroll(
  scrollTop: number,
  slotHeight: number,
  total: number,
): number {
  if (total <= 0) return 0;
  if (slotHeight <= 0) return 0;

  const index = Math.round(scrollTop / slotHeight);
  return Math.min(total - 1, Math.max(0, index));
}
