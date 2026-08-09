"use client";

import { useRef } from "react";
import { usePlayerControls, usePlayerState } from "./PlayerContext";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * The chapter-segmented scrubber (§7.4, signature moment 3).
 *
 * Segments come from generated chapters. When there are none — Class B content,
 * a talk still processing, or chapter detection below the confidence threshold —
 * it renders as a single unsegmented span, which is exactly the failure mode
 * §11 specifies rather than an error state.
 *
 * Marks are the citation ticks: the same primitive as the underline in an AI
 * answer, so clicking a citation and watching the tick appear here reads as one
 * object moving rather than two things happening.
 */

export type Chapter = { startSec: number; endSec: number; title: string };

type Props = {
  chapters?: Chapter[];
  /** Cited timestamps, in seconds. */
  marks?: number[];
  className?: string;
};

export function Scrubber({ chapters = [], marks = [], className }: Props) {
  const { seek } = usePlayerControls();
  const { currentTime, duration } = usePlayerState();
  const trackRef = useRef<HTMLDivElement>(null);

  if (duration <= 0) {
    return (
      <div
        className={cn("h-1 w-full rounded-(--radius-none) bg-rule", className)}
        aria-hidden="true"
      />
    );
  }

  const segments: Chapter[] =
    chapters.length > 0
      ? chapters
      : [{ startSec: 0, endSec: duration, title: "Full talk" }];

  function seekToClientX(clientX: number) {
    const track = trackRef.current;
    if (!track) return;
    const { left, width } = track.getBoundingClientRect();
    const fraction = Math.min(1, Math.max(0, (clientX - left) / width));
    seek(fraction * duration);
  }

  return (
    <div
      ref={trackRef}
      // A real slider role, so screen readers announce position and the arrow
      // keys work here even though the page-level bindings also handle them.
      role="slider"
      tabIndex={0}
      aria-label="Seek"
      aria-valuemin={0}
      aria-valuemax={Math.round(duration)}
      aria-valuenow={Math.round(currentTime)}
      aria-valuetext={`${formatTimecode(currentTime)} of ${formatTimecode(duration)}`}
      onPointerDown={(event) => {
        event.currentTarget.setPointerCapture(event.pointerId);
        seekToClientX(event.clientX);
      }}
      onPointerMove={(event) => {
        if (event.buttons === 1) seekToClientX(event.clientX);
      }}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
          event.preventDefault();
          seek(currentTime + (event.key === "ArrowRight" ? 5 : -5));
        }
      }}
      className={cn(
        "group relative flex h-6 w-full cursor-pointer items-center gap-[2px]",
        "touch-none select-none",
        className,
      )}
    >
      {segments.map((segment) => {
        const span = Math.max(0.001, segment.endSec - segment.startSec);
        const progress = Math.min(
          1,
          Math.max(0, (currentTime - segment.startSec) / span),
        );

        return (
          <div
            key={`${segment.startSec}-${segment.title}`}
            title={segment.title}
            style={{ flexGrow: span }}
            className="relative h-1 overflow-hidden rounded-(--radius-none) bg-rule transition-[height] group-hover:h-1.5"
          >
            {/* scaleX, not width — §7.3 allows transform and opacity only. */}
            <div
              aria-hidden="true"
              className="absolute inset-0 origin-left bg-screen"
              style={{ transform: `scaleX(${progress})` }}
            />
          </div>
        );
      })}

      {/* Citation marks sit above the track so a chapter boundary never hides
          one. The only chromatic object on the player. */}
      {marks.map((mark) => (
        <span
          key={mark}
          aria-hidden="true"
          className="absolute top-1/2 h-3 w-[2px] -translate-y-1/2 bg-citrine"
          style={{ left: `${Math.min(100, (mark / duration) * 100)}%` }}
        />
      ))}
    </div>
  );
}
