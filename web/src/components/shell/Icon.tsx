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
  | "shorts";

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
};

const FILLED: Partial<Record<IconName, boolean>> = {
  home: true,
  liked: true,
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
