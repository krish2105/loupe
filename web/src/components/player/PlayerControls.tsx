"use client";

import { Scrubber, type Chapter } from "./Scrubber";
import { usePlayerControls, usePlayerState } from "./PlayerContext";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * Player chrome.
 *
 * backdrop-filter appears here and on navigation only (§7.3) — never on the
 * grid, where it costs 15–30% FPS on a mid-tier Android.
 */

function ControlButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className="grid size-9 shrink-0 place-items-center rounded-(--radius-sm) text-screen/80 transition-colors hover:text-screen"
    >
      {children}
    </button>
  );
}

export function PlayerControls({
  chapters,
  marks,
  level,
  onFullscreen,
}: {
  chapters?: Chapter[];
  marks?: number[];
  /** Current rendition, e.g. "720p". Proof that ABR is doing something. */
  level?: string | null;
  onFullscreen: () => void;
}) {
  const { toggle } = usePlayerControls();
  const { currentTime, duration, isPlaying } = usePlayerState();

  return (
    <div
      className={cn(
        "absolute inset-x-0 bottom-0 z-10",
        "bg-gradient-to-t from-black/70 to-transparent px-3 pb-2 pt-8",
        "backdrop-blur-[2px]",
      )}
    >
      <Scrubber chapters={chapters} marks={marks} />

      <div className="mt-1 flex items-center gap-2">
        <ControlButton label={isPlaying ? "Pause" : "Play"} onClick={toggle}>
          <svg viewBox="0 0 20 20" aria-hidden="true" className="size-5" fill="currentColor">
            {isPlaying ? (
              <path d="M6 4h3v12H6zM11 4h3v12h-3z" />
            ) : (
              <path d="M6.5 4.2 15 10l-8.5 5.8z" />
            )}
          </svg>
        </ControlButton>

        <p className="font-mono text-(length:--step--2) text-screen/80 tabular-nums">
          {formatTimecode(currentTime)}
          <span className="text-screen/45"> / {formatTimecode(duration)}</span>
        </p>

        <div className="ml-auto flex items-center gap-2">
          {level && (
            <span className="font-mono text-(length:--step--2) text-screen/60">
              {level}
            </span>
          )}
          <ControlButton label="Full screen" onClick={onFullscreen}>
            <svg
              viewBox="0 0 20 20"
              aria-hidden="true"
              className="size-[18px]"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            >
              <path d="M7 3H3v4M13 3h4v4M7 17H3v-4M13 17h4v-4" />
            </svg>
          </ControlButton>
        </div>
      </div>
    </div>
  );
}
