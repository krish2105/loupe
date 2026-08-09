import { cn } from "@/lib/utils";

/**
 * The icon set.
 *
 * Hand-drawn on one 24×24 grid at one stroke weight. Still no icon dependency:
 * a dozen glyphs do not justify one, and a shared grid is what keeps a sidebar
 * of mixed shapes looking like a set rather than a collection.
 */

export type IconName =
  | "menu"
  | "home"
  | "subscriptions"
  | "history"
  | "playlists"
  | "watchLater"
  | "liked"
  | "create"
  | "bell"
  | "search"
  | "mic"
  | "user"
  | "chevronRight"
  | "shorts"
  | "volume"
  | "muted"
  | "play"
  | "pause"
  | "previous"
  | "next"
  | "rewind"
  | "forward"
  | "shuffle"
  | "repeat"
  | "repeat-one"
  | "queue"
  | "download"
  | "audio";

const PATHS: Record<IconName, React.ReactNode> = {
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  home: <path d="M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z" />,
  subscriptions: (
    <>
      <path d="M6 5.5h12M4 9h16" />
      <rect x="4" y="12" width="16" height="8" rx="2" />
      <path d="m10.8 14.6 3.4 1.9-3.4 1.9z" />
    </>
  ),
  history: (
    <>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1" />
      <path d="M3.5 4.5V9H8" />
      <path d="M12 7.5V12l3 1.8" />
    </>
  ),
  playlists: (
    <>
      <path d="M4 7h11M4 12h11M4 17h7" />
      <path d="m17 12.8 4 2.4-4 2.4z" />
    </>
  ),
  watchLater: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5.2l3.4 2" />
    </>
  ),
  liked: (
    <path d="M7 20V10l4.2-6a2 2 0 0 1 2.9 2.4L13 10h5.4a2 2 0 0 1 1.9 2.6l-1.8 5.8A2.4 2.4 0 0 1 16.2 20zM7 10H4.5v10H7z" />
  ),
  create: <path d="M12 5.5v13M5.5 12h13" />,
  bell: (
    <>
      <path d="M6.5 10a5.5 5.5 0 0 1 11 0c0 4 1.5 5.5 1.5 5.5H5s1.5-1.5 1.5-5.5z" />
      <path d="M10 19a2.2 2.2 0 0 0 4 0" />
    </>
  ),
  search: (
    <>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m15.8 15.8 4 4" />
    </>
  ),
  mic: (
    <>
      <rect x="9.5" y="3.5" width="5" height="10" rx="2.5" />
      <path d="M6 11.5a6 6 0 0 0 12 0M12 17.5V21" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8.5" r="3.75" />
      <path d="M5 20a7 7 0 0 1 14 0" />
    </>
  ),
  chevronRight: <path d="m9.5 6 6 6-6 6" />,
  shorts: (
    <>
      <rect x="7" y="2.5" width="10" height="19" rx="4" />
      <path d="M10.8 9.2 15 12l-4.2 2.8z" />
    </>
  ),
  volume: (
    <>
      <path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4z" />
      <path d="M15.5 9.5a3.5 3.5 0 0 1 0 5M18 7a7 7 0 0 1 0 10" />
    </>
  ),
  muted: (
    <>
      <path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4z" />
      <path d="m16 9.5 5 5M21 9.5l-5 5" />
    </>
  ),
  // Audio mode (ADR 0003). Same 24×24 grid and stroke weight as the rest, so
  // the transport controls read as part of the set rather than as an import.
  play: <path d="M8 5.5v13l11-6.5z" />,
  pause: <path d="M8.5 5.5h3v13h-3zM12.5 5.5h3v13h-3z" />,
  previous: <path d="M7 5.5v13h1.6v-13zM19 5.5 9.6 12l9.4 6.5z" />,
  next: <path d="M17 5.5v13h-1.6v-13zM5 5.5 14.4 12 5 18.5z" />,
  // The numbers are inside the glyph because "back fifteen" and "forward
  // thirty" are different actions, and two identical arrows facing opposite
  // ways make people guess.
  rewind: (
    <>
      <path d="M4.5 7.5A8 8 0 1 1 4 12" />
      <path d="M4.5 4v3.5H8" />
      <text
        x="12"
        y="15.5"
        textAnchor="middle"
        fontSize="7"
        fill="currentColor"
        stroke="none"
      >
        15
      </text>
    </>
  ),
  forward: (
    <>
      <path d="M19.5 7.5A8 8 0 1 0 20 12" />
      <path d="M19.5 4v3.5H16" />
      <text
        x="12"
        y="15.5"
        textAnchor="middle"
        fontSize="7"
        fill="currentColor"
        stroke="none"
      >
        30
      </text>
    </>
  ),
  shuffle: (
    <>
      <path d="M4 7h3.5l9 10H20M4 17h3.5l9-10H20" />
      <path d="m17.5 4.5 2.5 2.5-2.5 2.5M17.5 14.5l2.5 2.5-2.5 2.5" />
    </>
  ),
  repeat: (
    <>
      <path d="M6 8h12v4M18 16H6v-4" />
      <path d="m15.5 5.5 2.5 2.5-2.5 2.5M8.5 13.5 6 16l2.5 2.5" />
    </>
  ),
  "repeat-one": (
    <>
      <path d="M6 8h12v4M18 16H6v-4" />
      <path d="m15.5 5.5 2.5 2.5-2.5 2.5M8.5 13.5 6 16l2.5 2.5" />
      <text
        x="12"
        y="14.5"
        textAnchor="middle"
        fontSize="7"
        fill="currentColor"
        stroke="none"
      >
        1
      </text>
    </>
  ),
  queue: <path d="M4 7h11M4 12h11M4 17h7M17 11v8M17 11l4-1.5v8" />,
  download: <path d="M12 4v10M8 10.5l4 3.5 4-3.5M5 19h14" />,
  audio: (
    <>
      <path d="M5 10v4M9 7v10M13 5v14M17 8v8M21 11v2" />
    </>
  ),
};

const FILLED: Partial<Record<IconName, boolean>> = {
  home: true,
  liked: true,
  play: true,
  pause: true,
  previous: true,
  next: true,
};

export function Icon({
  name,
  className,
  filled,
}: {
  name: IconName;
  className?: string;
  /** Overrides the default; the sidebar fills the active item's glyph. */
  filled?: boolean;
}) {
  const isFilled = filled ?? FILLED[name] ?? false;

  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={cn("size-6 shrink-0", className)}
      fill={isFilled ? "currentColor" : "none"}
      stroke={isFilled ? "none" : "currentColor"}
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {PATHS[name]}
    </svg>
  );
}
