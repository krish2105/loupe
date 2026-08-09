"use client";

import {
  createContext,
  useContext,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import { PlayerStore, type PlayerSnapshot, type MediaLike } from "./player-store";

/**
 * React binding for the player store (§5.1).
 *
 * Two hooks on purpose:
 *
 *   usePlayerControls()  imperative, stable, never re-renders the caller
 *   usePlayerState()     subscribes, re-renders on change
 *
 * The split matters. A citation chip only ever *commands* the player — if it
 * subscribed to time it would re-render several times a second for no reason,
 * with a whole answer thread of chips behind it.
 */

type PlayerControls = Pick<
  PlayerStore,
  "seek" | "play" | "pause" | "toggle" | "nudge" | "attach" | "setMarks"
>;

const PlayerContext = createContext<PlayerStore | null>(null);

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  // A lazy useState initialiser, not a ref: refs must not be read during render,
  // and this runs exactly once per provider either way.
  const [store] = useState(() => new PlayerStore());

  return <PlayerContext value={store}>{children}</PlayerContext>;
}

/**
 * The raw store, for callers that need to observe playback without rendering
 * it — progress reporting being the case this exists for. Subscribing through
 * usePlayerState() there would re-render the whole video page several times a
 * second to feed a network write nobody looks at.
 */
export function usePlayerStore(): PlayerStore {
  return useStore();
}

function useStore(): PlayerStore {
  const store = useContext(PlayerContext);
  if (!store) {
    throw new Error(
      "Player hooks require a <PlayerProvider>. Wrap the video page in one.",
    );
  }
  return store;
}

/** Commands only. The returned object is referentially stable. */
export function usePlayerControls(): PlayerControls {
  const store = useStore();
  return useMemo(
    () => ({
      seek: store.seek,
      play: store.play,
      pause: store.pause,
      toggle: store.toggle,
      nudge: store.nudge,
      attach: store.attach,
      setMarks: store.setMarks,
    }),
    [store],
  );
}

/** Subscribes to playback state. Use only where the value is rendered. */
export function usePlayerState(): PlayerSnapshot {
  const store = useStore();
  return useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getServerSnapshot,
  );
}

export type { PlayerSnapshot, MediaLike };
