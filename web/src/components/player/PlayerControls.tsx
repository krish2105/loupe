"use client";

import { Scrubber, type Chapter } from "./Scrubber";
import { usePlayerControls, usePlayerState } from "./PlayerContext";
import { QualityMenu } from "./QualityMenu";
import type { HlsQuality } from "./useHls";
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
      className="grid size-9 shrink-0 place-items-center rounded-(--radius-sm) text-ink/80 transition-colors hover:text-ink"
    >
      {children}
    </button>
  );
}

export function PlayerControls({
  chapters,
  quality,
  onFullscreen,
}: {
  chapters?: Chapter[];
  /**
   * The rendition ladder and the current choice. This used to be a bare
   * `level` string rendered as a `<span>` — a resolution that looked exactly
   * like the quality button of every player people already use and did
   * nothing when pressed.
   */
  quality: HlsQuality;
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
        /**
         * The chrome is a dark context in both themes, because it sits on a
         * black scrim over video no matter what the page around it is doing.
         *
         * Without this every control here inherited the page's `--ink`, which
         * in light mode is #0f0f10 — near-black type on a near-black gradient.
         * The play button, the timecode, the quality control and the
         * full-screen button were all invisible in light theme, and had been
         * since the controls were built, because the player was only ever
         * looked at in the dark.
         *
         * Redefining the token rather than swapping each class means every
         * child keeps reading `text-ink` and needs no change. It is scoped to
         * the chrome rather than to the whole player, because the resume notice
         * floats over the same video on its own `bg-surface` and does want the
         * page's tokens — a container-wide override would need it to opt back
         * out, and there is no non-circular way to say "whatever the page said".
         */
        "[--ink:#f2f2f3]",
      )}
    >
      <Scrubber chapters={chapters} />

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

        <p className="font-mono text-(length:--step--2) text-ink/80 tabular-nums">
          {formatTimecode(currentTime)}
          <span className="text-ink/45"> / {formatTimecode(duration)}</span>
        </p>

        <div className="ml-auto flex items-center gap-2">
          <QualityMenu
            options={quality.options}
            selected={quality.selected}
            activeHeight={quality.activeHeight}
            onSelect={quality.select}
          />
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
