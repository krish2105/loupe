import { describe, expect, it } from "vitest";
import {
  EMPTY_QUEUE,
  RESTART_AFTER_SEC,
  addToQueue,
  currentId,
  nextCursor,
  playNext,
  playNow,
  previousAction,
  removeAt,
  reorder,
  setShuffle,
  shuffledOrder,
  upcoming,
  type QueueState,
} from "./queue-policy";

/**
 * Queue semantics (ADR 0003).
 *
 * These are the rules that are wrong in ways nobody notices until the fourth
 * track, which is exactly why they are pure functions rather than state inside
 * a component wired to an audio element.
 */

const EPISODES = ["a", "b", "c", "d", "e"];

function queue(overrides: Partial<QueueState> = {}): QueueState {
  return { ...playNow(EMPTY_QUEUE, EPISODES), ...overrides };
}

describe("shuffle is an ordering, not a random pick", () => {
  it("keeps every track exactly once", () => {
    const order = shuffledOrder(EPISODES.length, 42);

    expect([...order].sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 4]);
  });

  it("gives the same permutation for the same seed", () => {
    expect(shuffledOrder(8, 7)).toEqual(shuffledOrder(8, 7));
  });

  it("does not change what is playing when it is switched on", () => {
    // The failure this prevents: pressing shuffle mid-episode and having the
    // episode you are listening to stop.
    const playing = setShuffle({ ...queue(), cursor: 2 }, true, 99);

    expect(currentId(playing)).toBe("c");
  });

  it("keeps playing the same track when it is switched off", () => {
    const on = setShuffle({ ...queue(), cursor: 3 }, true, 5);
    const off = setShuffle(on, false, 5);

    expect(currentId(off)).toBe(currentId(on));
  });

  it("restores the queued order when switched off", () => {
    const off = setShuffle(setShuffle(queue(), true, 5), false, 5);

    expect(off.order).toEqual([0, 1, 2, 3, 4]);
  });
});

describe("advancing", () => {
  it("moves to the next track", () => {
    expect(nextCursor(queue(), { auto: false })).toBe(1);
  });

  it("stops at the end with repeat off", () => {
    expect(nextCursor(queue({ cursor: 4 }), { auto: true })).toBeNull();
  });

  it("wraps at the end with repeat all", () => {
    expect(nextCursor(queue({ cursor: 4, repeat: "all" }), { auto: true })).toBe(0);
  });

  it("repeats the same track when one ends on repeat one", () => {
    expect(nextCursor(queue({ cursor: 2, repeat: "one" }), { auto: true })).toBe(2);
  });

  it("still advances when next is pressed on repeat one", () => {
    /**
     * The distinction the `auto` flag exists for. Someone pressing next while
     * repeat-one is on wants the next track; playing the same one again makes
     * the button look broken.
     */
    expect(nextCursor(queue({ cursor: 2, repeat: "one" }), { auto: false })).toBe(3);
  });

  it("has nowhere to go in an empty queue", () => {
    expect(nextCursor(EMPTY_QUEUE, { auto: true })).toBeNull();
  });
});

describe("previous", () => {
  it("goes back a track near the start of one", () => {
    expect(previousAction(queue({ cursor: 2 }), 2)).toEqual({
      kind: "move",
      cursor: 1,
    });
  });

  it("restarts the current track once you are into it", () => {
    // Pressing previous halfway through a forty-minute episode to hear
    // something again must not take you to the wrong episode.
    expect(previousAction(queue({ cursor: 2 }), RESTART_AFTER_SEC + 1)).toEqual({
      kind: "restart",
    });
  });

  it("restarts rather than underflowing at the first track", () => {
    expect(previousAction(queue({ cursor: 0 }), 1)).toEqual({ kind: "restart" });
  });

  it("wraps to the last track at the start with repeat all", () => {
    expect(previousAction(queue({ cursor: 0, repeat: "all" }), 1)).toEqual({
      kind: "move",
      cursor: 4,
    });
  });
});

describe("queueing", () => {
  it("puts play-next immediately after the current track", () => {
    const next = playNext(queue({ cursor: 1 }), "new");

    expect(upcoming(next)[0]).toBe("new");
  });

  it("puts play-next in the right place while shuffled", () => {
    /**
     * The reason play-next is inserted into `order` and not into `items`.
     * Appending to items and hoping is how this feature ends up dropping the
     * track somewhere arbitrary in a shuffled queue.
     */
    const shuffled = setShuffle(queue({ cursor: 0 }), true, 3);
    const next = playNext(shuffled, "new");

    expect(upcoming(next)[0]).toBe("new");
  });

  it("puts add-to-queue at the end", () => {
    const added = addToQueue(queue({ cursor: 0 }), "new");

    expect(upcoming(added).at(-1)).toBe("new");
  });
});

describe("reordering", () => {
  it("moves a track", () => {
    const moved = reorder(queue({ cursor: 0 }), 3, 1);

    expect(moved.order).toEqual([0, 3, 1, 2, 4]);
  });

  it("does not change what is playing when something is dragged above it", () => {
    const moved = reorder(queue({ cursor: 2 }), 4, 0);

    expect(currentId(moved)).toBe("c");
  });

  it("ignores an out-of-range move rather than corrupting the order", () => {
    const before = queue();

    expect(reorder(before, 0, 99)).toBe(before);
    expect(reorder(before, -1, 0)).toBe(before);
  });
});

describe("removing", () => {
  it("keeps playing the same track when a different one is removed", () => {
    const removed = removeAt(queue({ cursor: 2 }), 4);

    expect(currentId(removed)).toBe("c");
  });

  it("moves to the next track when the playing one is removed", () => {
    const removed = removeAt(queue({ cursor: 2 }), 2);

    expect(currentId(removed)).toBe("d");
  });

  it("does not fall off the end when the last track is removed", () => {
    const removed = removeAt(queue({ cursor: 4 }), 4);

    expect(currentId(removed)).toBe("d");
  });
});

describe("the current track", () => {
  it("is nothing in an empty queue", () => {
    expect(currentId(EMPTY_QUEUE)).toBeNull();
  });

  it("is the one the cursor points at", () => {
    expect(currentId(queue({ cursor: 3 }))).toBe("d");
  });
});
