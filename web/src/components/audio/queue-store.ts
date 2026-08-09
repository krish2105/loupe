import {
  EMPTY_QUEUE,
  addToQueue,
  currentId,
  nextCursor,
  playNext,
  playNow,
  previousAction,
  removeAt,
  reorder,
  setShuffle,
  upcoming,
  type QueueState,
  type RepeatMode,
} from "./queue-policy";

/**
 * The queue store — framework-free, like the player store next to it.
 *
 * This started as React state inside a provider and the compiler was right to
 * reject it. A queue restored from localStorage is *external* state: it exists
 * before React renders, it outlives any component, and seeding React state from
 * it in an effect means the first render is wrong and the second one corrects
 * it. `useSyncExternalStore` over a plain object is what that shape actually
 * wants, and it is the same answer §5.1 reached for playback in week one.
 *
 * Every rule about ordering lives in queue-policy.ts. This holds state,
 * persists it, and notifies.
 */

export type QueueTrack = {
  id: string;
  title: string;
  channelName: string;
  channelHandle: string;
  durationSec: number | null;
  src: string;
};

export type QueueSnapshot = {
  state: QueueState;
  tracks: Record<string, QueueTrack>;
  current: QueueTrack | null;
  upcoming: QueueTrack[];
};

/**
 * Saved playhead per episode.
 *
 * Deliberately outside the snapshot. Positions are written every ten seconds
 * and read once per track change, which is the exact opposite access pattern to
 * the queue itself — putting them in the snapshot would re-render the bar and
 * the queue panel six times a minute to store a number nothing is displaying.
 */
type Positions = Record<string, number>;

/**
 * Bumping this discards every saved queue, which is the point.
 *
 * A track persists its `src`, so a queue written before a stream URL changed
 * replays the old one forever and no amount of fixing the database reaches it.
 * That is not hypothetical: the fixture stream had to move CDNs, and every
 * browser that had played anything kept requesting the dead one — the catalogue
 * was correct, the API was correct, and playback was still broken until site
 * data was cleared by hand.
 *
 * Nobody should have to clear site data to recover from a URL change, so the
 * version moves instead. Losing a queue is a small cost; a queue that cannot
 * play is a larger one. Resume positions come back from the API on the next
 * play, so nothing that took real effort to accumulate is lost here.
 *
 * Caching a URL with no expiry is the underlying flaw and it will bite again
 * when Bunny lands, because signed URLs expire on a timer rather than on a
 * deploy. The fix then is to stop persisting `src` and re-resolve it from the
 * catalogue on restore. Doing that now would mean building an async
 * re-resolution path for a provider that is not wired up yet.
 */
const STORAGE_KEY = "loupe.queue.v2";

/** Cycles in the order the button implies: none, then all, then just this one. */
const REPEAT_CYCLE: RepeatMode[] = ["off", "all", "one"];

const EMPTY_SNAPSHOT: QueueSnapshot = {
  state: EMPTY_QUEUE,
  tracks: {},
  current: null,
  upcoming: [],
};

export class QueueStore {
  private listeners = new Set<() => void>();
  private snapshot: QueueSnapshot = EMPTY_SNAPSHOT;
  private positions: Positions = {};
  private loaded = false;

  getSnapshot = (): QueueSnapshot => {
    // Read from storage once, on the first client read. Doing it in the
    // constructor would run during the server render, where localStorage does
    // not exist.
    if (!this.loaded) {
      this.loaded = true;
      this.restore();
    }
    return this.snapshot;
  };

  /** The server has no storage, so it renders an empty queue and no bar. */
  getServerSnapshot = (): QueueSnapshot => EMPTY_SNAPSHOT;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  private restore() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;

      const saved = JSON.parse(raw) as {
        state?: QueueState;
        tracks?: Record<string, QueueTrack>;
        positions?: Positions;
      };
      this.positions = saved.positions ?? {};

      if (!saved.state?.items?.length) return;

      this.snapshot = derive(saved.state, saved.tracks ?? {});
    } catch {
      // A corrupt or unreadable entry means starting empty, not crashing.
    }
  }

  private persist() {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          state: this.snapshot.state,
          tracks: this.snapshot.tracks,
          positions: this.positions,
        }),
      );
    } catch {
      // Private browsing and full quotas both throw here. Losing the queue on
      // reload is a much smaller failure than losing the page.
    }
  }

  private commit(state: QueueState, tracks = this.snapshot.tracks) {
    this.snapshot = derive(state, tracks);
    this.persist();
    for (const listener of this.listeners) listener();
  }

  private remember(incoming: QueueTrack[]): Record<string, QueueTrack> {
    const merged = { ...this.snapshot.tracks };
    for (const track of incoming) merged[track.id] = track;
    return merged;
  }

  playNow = (incoming: QueueTrack[], startAt = 0): void => {
    const tracks = this.remember(incoming);
    const ids = incoming.map((track) => track.id);
    this.commit(playNow(this.snapshot.state, ids, startAt, seedFrom(ids)), tracks);
  };

  playNext = (track: QueueTrack): void => {
    this.commit(playNext(this.snapshot.state, track.id), this.remember([track]));
  };

  addToQueue = (track: QueueTrack): void => {
    this.commit(addToQueue(this.snapshot.state, track.id), this.remember([track]));
  };

  /**
   * @param auto true when a track ended by itself, false when someone pressed
   *   next. Only repeat-one reads it, and getting it backwards makes the next
   *   button look broken.
   */
  advance = (auto: boolean): void => {
    const cursor = nextCursor(this.snapshot.state, { auto });
    if (cursor === null) return;
    this.commit({ ...this.snapshot.state, cursor });
  };

  /** Returns "restart" when the caller should seek to zero instead. */
  previous = (positionSec: number): "restart" | "moved" => {
    const action = previousAction(this.snapshot.state, positionSec);
    if (action.kind === "restart") return "restart";

    this.commit({ ...this.snapshot.state, cursor: action.cursor });
    return "moved";
  };

  jumpTo = (cursor: number): void => {
    this.commit({ ...this.snapshot.state, cursor });
  };

  remove = (position: number): void => {
    this.commit(removeAt(this.snapshot.state, position));
  };

  move = (from: number, to: number): void => {
    this.commit(reorder(this.snapshot.state, from, to));
  };

  toggleShuffle = (): void => {
    const state = this.snapshot.state;
    this.commit(setShuffle(state, !state.shuffle, seedFrom(state.items)));
  };

  cycleRepeat = (): void => {
    const state = this.snapshot.state;
    const at = REPEAT_CYCLE.indexOf(state.repeat);
    this.commit({ ...state, repeat: REPEAT_CYCLE[(at + 1) % REPEAT_CYCLE.length]! });
  };

  clear = (): void => {
    // Positions survive clearing the queue. Someone emptying a queue is saying
    // "not these, next" — not "forget where I was in the episode I was
    // halfway through".
    this.commit(EMPTY_QUEUE, {});
  };

  /** Where this episode was left, if anywhere. */
  positionFor = (videoId: string): number | null => {
    this.getSnapshot(); // Forces the lazy restore on a first read.
    return this.positions[videoId] ?? null;
  };

  /**
   * Record the playhead.
   *
   * Persists without notifying. Nothing renders this, and waking every
   * subscriber to write a number to storage would make the bar and the queue
   * panel re-render on a timer.
   *
   * Callers throttle. ProgressReporter already decides when a position is worth
   * writing, and this reuses that judgement rather than inventing a second one.
   */
  rememberPosition = (videoId: string, seconds: number): void => {
    this.getSnapshot();
    this.positions[videoId] = Math.floor(seconds);
    this.persist();
  };

  /** Called when an episode finishes, so it does not resume onto its own end. */
  forgetPosition = (videoId: string): void => {
    this.getSnapshot();
    delete this.positions[videoId];
    this.persist();
  };
}

function derive(
  state: QueueState,
  tracks: Record<string, QueueTrack>,
): QueueSnapshot {
  const id = currentId(state);

  return {
    state,
    tracks,
    current: id ? (tracks[id] ?? null) : null,
    upcoming: upcoming(state)
      .map((trackId) => tracks[trackId])
      .filter((track): track is QueueTrack => track !== undefined),
  };
}

/**
 * A shuffle seed derived from the queue itself.
 *
 * Deterministic on purpose: a queue restored from storage shuffles the same way
 * it did before the reload, so the order someone was listening to survives.
 */
function seedFrom(ids: string[]): number {
  let hash = 2166136261;
  for (const id of ids) {
    for (let index = 0; index < id.length; index++) {
      hash ^= id.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
  }
  return hash >>> 0;
}
