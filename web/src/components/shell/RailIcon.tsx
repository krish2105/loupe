/**
 * Rail glyphs.
 *
 * Hand-drawn rather than pulled from an icon package: six icons do not justify
 * a dependency, and a shared 20×20 grid with one stroke weight keeps the rail
 * visually quiet, which is what §7.2 asks of the chrome.
 */

export type RailIconName =
  | "home"
  | "shorts"
  | "subscriptions"
  | "history"
  | "saved"
  | "playlists";

const PATHS: Record<RailIconName, React.ReactNode> = {
  home: <path d="M3 8.5 10 3l7 5.5V16a1 1 0 0 1-1 1h-3.5v-5h-5v5H4a1 1 0 0 1-1-1z" />,
  shorts: (
    <>
      <rect x="6" y="2.5" width="8" height="15" rx="3.2" />
      <path d="M8.8 7.6 12.2 10l-3.4 2.4z" />
    </>
  ),
  subscriptions: (
    <>
      <path d="M4 6.5h12M2.5 10h15M4 13.5h12" />
      <path d="M9 16.5h2" />
    </>
  ),
  history: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 6v4.2l2.8 1.7" />
    </>
  ),
  saved: <path d="M5.5 3h9v14l-4.5-3.4L5.5 17z" />,
  playlists: (
    <>
      <path d="M3 5.5h9M3 10h9M3 14.5h5" />
      <path d="m14 9.5 4 2.4-4 2.4z" />
    </>
  ),
};

export function RailIcon({ name }: { name: RailIconName }) {
  const filled = name === "home" || name === "saved";

  return (
    <svg
      viewBox="0 0 20 20"
      aria-hidden="true"
      className="size-[19px]"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={filled ? 0 : 1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {PATHS[name]}
    </svg>
  );
}
