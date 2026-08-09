/**
 * Keyboard bindings for the player (§9.1).
 *
 * A pure mapping from key to intent, deliberately separated from the DOM so the
 * whole contract is testable. Space, arrows, J/K/L, F, M, and number-key seek
 * are all specified behaviour, and "the shortcuts work" is the kind of claim
 * that quietly stops being true.
 */

export type PlayerAction =
  | { type: "toggle" }
  | { type: "nudge"; seconds: number }
  | { type: "seekFraction"; fraction: number }
  | { type: "volume"; delta: number }
  | { type: "fullscreen" }
  | { type: "mute" };

/** Modifier state, named so callers can pass a real KeyboardEvent unchanged. */
export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
}

/**
 * True when the key belongs to whatever the person is typing into rather than
 * to the player. Without this, pressing space while searching pauses the video
 * and inserts nothing — the single most irritating bug in this class of UI.
 */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;

  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

export function keyToAction(event: KeyLike): PlayerAction | null {
  // Never shadow a browser or OS shortcut.
  if (event.ctrlKey || event.metaKey || event.altKey) return null;

  switch (event.key) {
    case " ":
    case "Spacebar":
    case "k":
    case "K":
      return { type: "toggle" };

    case "ArrowLeft":
      return { type: "nudge", seconds: -5 };
    case "ArrowRight":
      return { type: "nudge", seconds: 5 };

    // The editing-suite convention: J and L scrub in larger steps than the
    // arrows, which is why both exist rather than being duplicates.
    case "j":
    case "J":
      return { type: "nudge", seconds: -10 };
    case "l":
    case "L":
      return { type: "nudge", seconds: 10 };

    case "ArrowUp":
      return { type: "volume", delta: 0.1 };
    case "ArrowDown":
      return { type: "volume", delta: -0.1 };

    case "f":
    case "F":
      return { type: "fullscreen" };
    case "m":
    case "M":
      return { type: "mute" };

    default: {
      // 0–9 seek to that tenth of the talk.
      if (event.key.length === 1 && event.key >= "0" && event.key <= "9") {
        return { type: "seekFraction", fraction: Number(event.key) / 10 };
      }
      return null;
    }
  }
}
