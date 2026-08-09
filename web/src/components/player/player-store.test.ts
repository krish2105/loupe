import { describe, expect, it, vi } from "vitest";
import { PlayerStore, type MediaLike } from "./player-store";

/**
 * A stand-in for HTMLMediaElement.
 *
 * The behaviour that matters is not the DOM — it is that writing currentTime
 * seeks in place, and that writes before metadata do not stick. Faking it keeps
 * the citation-seek contract testable in CI without a browser.
 */
function fakeMedia(overrides: Partial<{ duration: number; readyState: number }> = {}) {
  const listeners = new Map<string, Set<() => void>>();

  const media = {
    currentTime: 0,
    duration: overrides.duration ?? 600,
    paused: true,
    readyState: overrides.readyState ?? 1,
    play: vi.fn(function (this: typeof media) {
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
