/**
 * The player store — §5.1, "player abstraction from day one".
 *
 * A single source of playback truth exposing seek, play, pause, and current
 * time. The AI panel, chapter list, and scrubber all consume it. The plan says
 * to build this in week 1 even though it is not needed until week 6, because
 * without it the citation-seek feature becomes prop-drilling spaghetti.
 *
 * Deliberately framework-free. React binds to it in PlayerContext.tsx; keeping
 * the logic out of a component is what lets the seek contract — the thing
 * §11.1 says the entire intelligence layer's credibility rests on — be tested
 * without a browser.
 */

/** The slice of HTMLMediaElement this store needs. Narrow, so tests can fake it. */
export interface MediaLike {
  currentTime: number;
  readonly duration: number;
  readonly paused: boolean;
  readonly readyState: number;
  play(): Promise<void> | void;
  pause(): void;
  addEventListener(type: string, listener: () => void): void;
  removeEventListener(type: string, listener: () => void): void;
}

export type PlayerSnapshot = {
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  /** True once metadata has loaded and a seek will land where it is asked to. */
  isReady: boolean;
  /**
   * Cited timestamps, in seconds.
   *
   * They live here rather than in the AI panel because the scrubber and the
   * answer have to agree — §7.4's citation-seek is "one object, two places",
   * and two components each holding their own copy is how the tick on the
   * timeline and the mark in the sentence quietly stop matching.
   */
  marks: number[];
};

const EMPTY: PlayerSnapshot = {
  currentTime: 0,
  duration: 0,
  isPlaying: false,
  isReady: false,
  marks: [],
};

/** HTMLMediaElement.HAVE_METADATA. Below this, currentTime writes do not stick. */
const HAVE_METADATA = 1;

const MEDIA_EVENTS = [
  "timeupdate",
  "durationchange",
  "loadedmetadata",
  "play",
  "playing",
  "pause",
  "ended",
  "seeked",
  "emptied",
] as const;

export class PlayerStore {
  private media: MediaLike | null = null;
  private listeners = new Set<() => void>();
  private snapshot: PlayerSnapshot = EMPTY;

  /**
   * A seek requested before metadata exists. §11.1 requires a citation to land
   * on the right moment; a person can click a citation while the manifest is
   * still loading, so the request is held rather than dropped.
   */
  private pendingSeek: number | null = null;

  /**
   * Called when a track finishes.
   *
   * A separate channel from `subscribe`, because "the media reached its end" is
   * an event and the snapshot is a state. A queue that inferred the end from
   * state would have to watch for currentTime approaching duration, which is
   * unreliable at the boundary and fires nothing at all on a stream whose
   * duration is not known.
   *
   * This exists so the queue can advance without the media element being
   * public. The element stays private, which is the entire point of §5.1's
   * abstraction: the queue was not designed until eleven phases after the store
   * was, and it still does not get to touch the DOM.
   */
  private endedListeners = new Set<() => void>();

  onEnded = (listener: () => void): (() => void) => {
    this.endedListeners.add(listener);
    return () => {
      this.endedListeners.delete(listener);
    };
  };

  getSnapshot = (): PlayerSnapshot => this.snapshot;

  /** Server render has no media element, so it sees the empty snapshot. */
  getServerSnapshot = (): PlayerSnapshot => EMPTY;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /** Binds to a media element. Returns the detach function. */
  attach = (media: MediaLike | null): (() => void) => {
    this.detach();
    if (!media) return () => {};

    this.media = media;
    const onEvent = () => this.sync();
    for (const event of MEDIA_EVENTS) media.addEventListener(event, onEvent);

    const onEnded = () => {
      for (const listener of this.endedListeners) listener();
    };
    media.addEventListener("ended", onEnded);

    this.sync();
    this.flushPendingSeek();

    return () => {
      for (const event of MEDIA_EVENTS) media.removeEventListener(event, onEvent);
      media.removeEventListener("ended", onEnded);
      if (this.media === media) {
        this.media = null;
        this.publish(EMPTY);
      }
    };
  };

  private detach() {
    this.media = null;
  }

  /**
   * Move the playhead. Consumed by the AI panel's citation chips, the chapter
   * list, and the scrubber.
   *
   * §9.1: must be smooth, never a reload. Writing currentTime on a live element
   * is exactly that — the HLS buffer is preserved and no manifest is refetched.
   */
  seek = (seconds: number): void => {
    const target = Math.max(0, seconds);

    if (!this.media || this.media.readyState < HAVE_METADATA) {
      this.pendingSeek = target;
      return;
    }

    this.media.currentTime = this.clampToDuration(target);
    this.sync();
  };

  play = (): void => {
    const started = this.media?.play();

    // play() returns a promise that rejects with AbortError whenever it is
    // interrupted — by a pause, a seek, or a source change. Every one of those
    // is normal here, since a citation click seeks and plays in the same tick.
    // Without this catch it surfaces as an unhandled rejection in the console.
    if (started && typeof started.catch === "function") {
      started.catch(() => {});
    }

    this.sync();
  };

  pause = (): void => {
    this.media?.pause();
    this.sync();
  };

  toggle = (): void => {
    if (!this.media) return;
    if (this.media.paused) this.play();
    else this.pause();
  };

  /** Relative seek, for the arrow-key and J/L bindings in §9.1. */
  nudge = (deltaSeconds: number): void => {
    this.seek(this.snapshot.currentTime + deltaSeconds);
  };

  /** Replace the cited timestamps shown on the scrubber. */
  setMarks = (marks: number[]): void => {
    const next = [...marks].sort((a, b) => a - b);
    const current = this.snapshot.marks;

    if (
      next.length === current.length &&
      next.every((value, index) => value === current[index])
    ) {
      return;
    }

    this.snapshot = { ...this.snapshot, marks: next };
    for (const listener of this.listeners) listener();
  };

  private clampToDuration(seconds: number): number {
    const { duration } = this.media ?? {};
    if (typeof duration !== "number" || !Number.isFinite(duration) || duration <= 0) {
      return seconds;
    }
    // Landing exactly on duration fires `ended`, which is not what a citation
    // near the end of a talk should do.
    return Math.min(seconds, duration - 0.05);
  }

  private flushPendingSeek() {
    if (this.pendingSeek === null) return;
    if (!this.media || this.media.readyState < HAVE_METADATA) return;

    const target = this.pendingSeek;
    this.pendingSeek = null;
    this.media.currentTime = this.clampToDuration(target);
    this.sync();
  }

  private sync() {
    const media = this.media;
    if (!media) {
      this.publish({ ...EMPTY, marks: this.snapshot.marks });
      return;
    }

    const isReady = media.readyState >= HAVE_METADATA;
    if (isReady) this.flushPendingSeek();

    this.publish({
      currentTime: media.currentTime,
      duration: Number.isFinite(media.duration) ? media.duration : 0,
      isPlaying: !media.paused,
      isReady,
      // Carried forward: a timeupdate must not wipe the citations.
      marks: this.snapshot.marks,
    });
  }

  /**
   * Publishes only on real change. useSyncExternalStore compares snapshots by
   * reference, so returning a fresh object every timeupdate would re-render
   * every subscriber four times a second whether or not anything moved.
   */
  private publish(next: PlayerSnapshot) {
    const prev = this.snapshot;
    if (
      prev.currentTime === next.currentTime &&
      prev.duration === next.duration &&
      prev.isPlaying === next.isPlaying &&
      prev.isReady === next.isReady &&
      prev.marks === next.marks
    ) {
      return;
    }
    this.snapshot = next;
    for (const listener of this.listeners) listener();
  }
}
