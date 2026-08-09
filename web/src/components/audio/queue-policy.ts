/**
 * The queue — ADR 0003's audio mode.
 *
 * Pure functions over plain data, for the same reason the shorts window policy
 * is: the semantics of shuffle and repeat are fiddly, wrong in ways nobody
 * notices until the fourth track, and impossible to test at all once they are
 * tangled up with an audio element and React state.
 *
 * The one decision everything here follows from: **shuffle is an ordering, not
 * a random pick.** A player that chooses a random track on every advance can
 * play the same track twice in a row and cannot implement "previous" at all.
 * So shuffling permutes an index order once, and advancing walks that order.
 * This is what every music player people actually like does, and it is also the
 * only version that makes `previous` mean anything.
 */

export type RepeatMode = "off" | "all" | "one";

export type QueueState = {
  /** Content ids, in the order they were queued. Never reordered by shuffle. */
  items: string[];
  /** Position within `order`, not within `items`. */
  cursor: number;
  /** Indices into `items`. Identity when shuffle is off, a permutation when on. */
  order: number[];
  shuffle: boolean;
  repeat: RepeatMode;
};

export const EMPTY_QUEUE: QueueState = {
  items: [],
  cursor: 0,
  order: [],
  shuffle: false,
  repeat: "off",
};

export function currentId(queue: QueueState): string | null {
  const index = queue.order[queue.cursor];
  return index === undefined ? null : (queue.items[index] ?? null);
}

/**
 * A seeded shuffle.
 *
 * Seeded rather than `Math.random()` so a queue can be restored from storage
 * and produce the same order, and so these tests assert on an order rather than
 * on statistical properties. Fisher-Yates, which is the one that is actually
 * uniform.
 */
export function shuffledOrder(
  length: number,
  seed: number,
  keepFirst?: number,
): number[] {
  const order = Array.from({ length }, (_, index) => index);

  // Deterministic PRNG (mulberry32). Any decent one would do; the property that
  // matters is that the same seed gives the same permutation.
  let state = seed >>> 0;
  const next = () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(next() * (i + 1));
    [order[i], order[j]] = [order[j]!, order[i]!];
  }

  // Turning shuffle on mid-track must not change what is playing. The current
  // track moves to the front of the new order and everything else is shuffled
  // around it.
  if (keepFirst !== undefined) {
    const at = order.indexOf(keepFirst);
    if (at > 0) {
      order.splice(at, 1);
      order.unshift(keepFirst);
    }
  }

  return order;
}

export function setShuffle(
  queue: QueueState,
  shuffle: boolean,
  seed: number,
): QueueState {
  if (shuffle === queue.shuffle) return queue;

  const playing = queue.order[queue.cursor];

  if (!shuffle) {
    // Returning to queued order keeps playing what is playing, so the cursor
    // moves to wherever that track sits in the natural order rather than
    // resetting to zero.
    return {
      ...queue,
      shuffle: false,
      order: queue.items.map((_, index) => index),
      cursor: playing ?? 0,
    };
  }

  return {
    ...queue,
    shuffle: true,
    order: shuffledOrder(queue.items.length, seed, playing),
    cursor: 0,
  };
}

/**
 * What plays when this one ends, or when someone presses next.
 *
 * `auto` distinguishes the two, and only one thing depends on it: repeat-one
 * repeats on natural end and is ignored on an explicit press. Someone pressing
 * next while repeat-one is on wants the next track, not the same one again.
 * Getting this backwards makes the button look broken.
 */
export function nextCursor(
  queue: QueueState,
  { auto }: { auto: boolean },
): number | null {
  if (queue.order.length === 0) return null;
  if (auto && queue.repeat === "one") return queue.cursor;

  const next = queue.cursor + 1;
  if (next < queue.order.length) return next;

  // Past the end. Repeat-all wraps; repeat-one wraps too, because a one-track
  // queue on repeat-one has nowhere else to go and stopping would be strange.
  if (queue.repeat === "all" || queue.repeat === "one") return 0;
  return null;
}

/**
 * Previous, with the restart rule every music player has.
 *
 * Under `restartAfterSec` into a track, previous goes back a track. Past it,
 * previous restarts the current one. Without this, pressing previous halfway
 * through a forty-minute episode to hear something again takes you to the
 * wrong episode.
 */
export const RESTART_AFTER_SEC = 5;

export function previousAction(
  queue: QueueState,
  positionSec: number,
): { kind: "restart" } | { kind: "move"; cursor: number } {
  if (positionSec > RESTART_AFTER_SEC) return { kind: "restart" };
  if (queue.cursor > 0) return { kind: "move", cursor: queue.cursor - 1 };
  if (queue.repeat === "all" && queue.order.length > 0) {
    return { kind: "move", cursor: queue.order.length - 1 };
  }
  return { kind: "restart" };
}

/** Replace the queue and start at a chosen track. */
export function playNow(
  queue: QueueState,
  items: string[],
  startAt = 0,
  seed = 1,
): QueueState {
  const order = queue.shuffle
    ? shuffledOrder(items.length, seed, startAt)
    : items.map((_, index) => index);

  return {
    ...queue,
    items,
    order,
    cursor: queue.shuffle ? 0 : startAt,
  };
}

/**
 * Play next: immediately after the current track, not at the end.
 *
 * Inserted into `order` rather than into `items`, which is the only way it can
 * mean "next" while shuffle is on. Appending to `items` and hoping is how this
 * feature ends up putting the track somewhere arbitrary.
 */
export function playNext(queue: QueueState, id: string): QueueState {
  const items = [...queue.items, id];
  const order = [...queue.order];
  order.splice(queue.cursor + 1, 0, items.length - 1);
  return { ...queue, items, order };
}

export function addToQueue(queue: QueueState, id: string): QueueState {
  const items = [...queue.items, id];
  return { ...queue, items, order: [...queue.order, items.length - 1] };
}

/** Move a track within the visible queue, which is `order`. */
export function reorder(queue: QueueState, from: number, to: number): QueueState {
  if (from === to) return queue;
  if (from < 0 || from >= queue.order.length) return queue;
  if (to < 0 || to >= queue.order.length) return queue;

  const order = [...queue.order];
  const [moved] = order.splice(from, 1);
  order.splice(to, 0, moved!);

  // The cursor follows the playing track rather than staying at its index.
  // Dragging something above what is playing must not change what is playing.
  const playing = queue.order[queue.cursor];
  const cursor = playing === undefined ? queue.cursor : order.indexOf(playing);

  return { ...queue, order, cursor: cursor < 0 ? queue.cursor : cursor };
}

export function removeAt(queue: QueueState, position: number): QueueState {
  if (position < 0 || position >= queue.order.length) return queue;

  const playing = queue.order[queue.cursor];
  const order = [...queue.order];
  const [removed] = order.splice(position, 1);

  // Items are never spliced, because every entry in `order` is an index into
  // them and removing one would silently repoint the rest. The orphaned entry
  // costs a string.
  const cursor =
    removed === playing
      ? Math.min(position, Math.max(0, order.length - 1))
      : Math.max(0, order.indexOf(playing ?? -1));

  return { ...queue, order, cursor };
}

/** The queue as someone sees it: upcoming ids, in play order. */
export function upcoming(queue: QueueState): string[] {
  return queue.order
    .slice(queue.cursor + 1)
    .map((index) => queue.items[index])
    .filter((id): id is string => id !== undefined);
}
