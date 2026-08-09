"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import { QueueStore, type QueueSnapshot, type QueueTrack } from "./queue-store";
import { usePlayerControls, usePlayerStore } from "@/components/player/PlayerContext";

/**
 * React binding for the queue (ADR 0003).
 *
 * The same two-hook split as the player: commands are stable and never
 * re-render their caller, state subscribes. A "play next" button on a card
 * should not re-render every time the cursor moves.
 */

type QueueControls = {
  playNow: (tracks: QueueTrack[], startAt?: number) => void;
  playNext: (track: QueueTrack) => void;
  addToQueue: (track: QueueTrack) => void;
  next: () => void;
  previous: () => void;
  jumpTo: (cursor: number) => void;
  remove: (position: number) => void;
  move: (from: number, to: number) => void;
  toggleShuffle: () => void;
  cycleRepeat: () => void;
  clear: () => void;
};

const QueueContext = createContext<QueueStore | null>(null);

export function QueueProvider({ children }: { children: React.ReactNode }) {
  // Lazy initialiser rather than a ref: refs must not be read during render,
  // and this runs exactly once per provider either way.
  const [store] = useState(() => new QueueStore());
  const player = usePlayerStore();

  // The end of a track is the only thing the queue needs from playback, and it
  // arrives as an event rather than by reaching for the media element. The
  // element stays private inside the player store, which is what lets a feature
  // designed eleven phases later consume it without touching the DOM.
  useEffect(() => player.onEnded(() => store.advance(true)), [player, store]);

  return <QueueContext value={store}>{children}</QueueContext>;
}

function useStore(): QueueStore {
  const store = useContext(QueueContext);
  if (!store) {
    throw new Error("Queue hooks require a <QueueProvider>.");
  }
  return store;
}

/** Subscribes to the queue. Use only where the value is rendered. */
export function useQueueState(): QueueSnapshot {
  const store = useStore();
  return useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot,
  );
}

/** Commands only. The returned object is referentially stable. */
export function useQueueControls(): QueueControls {
  const store = useStore();
  const player = usePlayerStore();
  const { seek, play } = usePlayerControls();

  const previous = useCallback(() => {
    // "Previous" needs the playhead, which is the player's business, so the
    // rule lives in the policy and this supplies the position.
    const outcome = store.previous(player.getSnapshot().currentTime);
    if (outcome === "restart") {
      seek(0);
      void play();
    }
  }, [store, player, seek, play]);

  return useMemo(
    () => ({
      playNow: store.playNow,
      playNext: store.playNext,
      addToQueue: store.addToQueue,
      next: () => store.advance(false),
      previous,
      jumpTo: store.jumpTo,
      remove: store.remove,
      move: store.move,
      toggleShuffle: store.toggleShuffle,
      cycleRepeat: store.cycleRepeat,
      clear: store.clear,
    }),
    [store, previous],
  );
}

export type { QueueTrack };
