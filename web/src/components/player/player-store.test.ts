import { describe, expect, it, vi } from "vitest";
import { PlayerStore, type MediaLike } from "./player-store";

/**
 * A stand-in for HTMLMediaElement.
 *
 * The behaviour that matters is not the DOM — it is that writing currentTime
 * seeks in place, and that writes before metadata do not stick. Faking it keeps
 * the citation-seek contract testable in CI without a browser.
 */
function fakeMedia(
  overrides: Partial<{
    duration: number;
    readyState: number;
    /** Reproduces the AbortError a real element throws on an interrupted play. */
    playRejects: boolean;
  }> = {},
) {
  const listeners = new Map<string, Set<() => void>>();

  const media = {
    currentTime: 0,
    playbackRate: 1,
    duration: overrides.duration ?? 600,
    paused: true,
    readyState: overrides.readyState ?? 1,
    play: vi.fn((): Promise<void> | void => {
      if (overrides.playRejects) {
        return Promise.reject(new DOMException("interrupted", "AbortError"));
      }
      media.paused = false;
      media.emit("play");
    }),
    pause: vi.fn(function () {
      media.paused = true;
      media.emit("pause");
    }),
    addEventListener(type: string, listener: () => void) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type)!.add(listener);
    },
    removeEventListener(type: string, listener: () => void) {
      listeners.get(type)?.delete(listener);
    },
    emit(type: string) {
      listeners.get(type)?.forEach((l) => l());
    },
    listenerCount() {
      let total = 0;
      for (const set of listeners.values()) total += set.size;
      return total;
    },
  };

  return media as typeof media & MediaLike;
}

describe("PlayerStore", () => {
  it("seeks in place rather than reloading (§9.1)", () => {
    const store = new PlayerStore();
    const media = fakeMedia();
    store.attach(media);

    store.seek(142.5);

    expect(media.currentTime).toBe(142.5);
    expect(store.getSnapshot().currentTime).toBe(142.5);
    // A reload would have meant re-attaching or touching src. Neither happened.
    expect(media.play).not.toHaveBeenCalled();
  });

  it("holds a seek requested before metadata and applies it on load", () => {
    const store = new PlayerStore();
    const media = fakeMedia({ readyState: 0 });
    store.attach(media);

    // A citation clicked while the manifest is still loading.
    store.seek(88);
    expect(media.currentTime).toBe(0);

    media.readyState = 1;
    media.emit("loadedmetadata");

    expect(media.currentTime).toBe(88);
  });

  it("clamps a seek past the end so it does not fire `ended`", () => {
    const store = new PlayerStore();
    const media = fakeMedia({ duration: 100 });
    store.attach(media);

    store.seek(500);

    expect(media.currentTime).toBeLessThan(100);
    expect(media.currentTime).toBeCloseTo(99.95, 2);
  });

  it("never seeks to a negative time", () => {
    const store = new PlayerStore();
    const media = fakeMedia();
    store.attach(media);

    store.nudge(-30);

    expect(media.currentTime).toBe(0);
  });

  it("notifies subscribers only when something actually changed", () => {
    const store = new PlayerStore();
    const media = fakeMedia();
    store.attach(media);

    const listener = vi.fn();
    store.subscribe(listener);

    media.currentTime = 10;
    media.emit("timeupdate");
    expect(listener).toHaveBeenCalledTimes(1);

    // Same position reported again — a real timeupdate does this constantly
    // while paused. Re-rendering every subscriber for it is the bug this guards.
    media.emit("timeupdate");
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("reflects play and pause state", () => {
    const store = new PlayerStore();
    const media = fakeMedia();
    store.attach(media);

    store.play();
    expect(store.getSnapshot().isPlaying).toBe(true);

    store.toggle();
    expect(store.getSnapshot().isPlaying).toBe(false);
  });

  it("removes every listener on detach", () => {
    const store = new PlayerStore();
    const media = fakeMedia();

    const detach = store.attach(media);
    expect(media.listenerCount()).toBeGreaterThan(0);

    detach();
    expect(media.listenerCount()).toBe(0);
    expect(store.getSnapshot().isReady).toBe(false);
  });

  it("swallows the AbortError play() throws when interrupted", async () => {
    const store = new PlayerStore();
    // A citation click seeks and plays in the same tick, which is exactly the
    // sequence that makes play() reject. Unhandled, it hits the console.
    const media = fakeMedia({ playRejects: true });

    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);

    store.attach(media);
    expect(() => store.play()).not.toThrow();
    await new Promise((resolve) => setTimeout(resolve, 10));

    process.off("unhandledRejection", unhandled);
    expect(unhandled).not.toHaveBeenCalled();
  });

  it("survives having no media element at all", () => {
    const store = new PlayerStore();

    // Class B content shows a third-party embed and the custom player is absent
    // (§9.1). Commands must be inert, not throw.
    expect(() => {
      store.seek(10);
      store.play();
      store.pause();
      store.toggle();
    }).not.toThrow();
  });
});


describe("playback speed", () => {
  it("applies to the element", () => {
    const store = new PlayerStore();
    const media = fakeMedia();
    store.attach(media);

    store.setRate(1.5);

    expect(media.playbackRate).toBe(1.5);
    expect(store.getSnapshot().rate).toBe(1.5);
  });

  it("survives a track change", () => {
    /**
     * Loading a new source resets the element to 1×. Someone who chose 1.5×
     * did not choose it for one episode, and the local copy this replaced lost
     * it every time the queue advanced.
     */
    const store = new PlayerStore();
    store.attach(fakeMedia());
    store.setRate(1.75);

    const next = fakeMedia();
    store.attach(next);

    expect(next.playbackRate).toBe(1.75);
    expect(store.getSnapshot().rate).toBe(1.75);
  });

  it("is remembered with no element attached", () => {
    const store = new PlayerStore();
    store.setRate(2);

    expect(store.getSnapshot().rate).toBe(2);
  });

  it("refuses a rate the element would reject", () => {
    // Media elements throw on a non-positive rate and stop decoding audio well
    // above 4×. Clamping is cheaper than a try/catch around every caller.
    const store = new PlayerStore();

    store.setRate(0);
    expect(store.getSnapshot().rate).toBe(0.25);

    store.setRate(99);
    expect(store.getSnapshot().rate).toBe(4);
  });
});
