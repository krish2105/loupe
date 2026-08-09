"use client";

import { useEffect, useRef } from "react";
import { usePlayerControls, usePlayerState } from "@/components/player/PlayerContext";
import type { Line } from "@/lib/audio";
import { activeLine } from "./transcript-policy";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * The transcript, following playback (ADR 0003).
 *
 * The feature that makes the case for spoken audio over CC music. In a music
 * app this panel is lyrics and needs licensed data; here it is a transcript
 * Loupe already produced, with timestamps it already stores, and every line is
 * a seek.
 *
 * Two things that are easy to get wrong and are handled explicitly.
 *
 * Lines are built from word timings, not from retrieval chunks. A chunk is 300
 * to 600 tokens because that is what a question needs answering from, and using
 * it as the reading unit put three and a half minutes of speech on one line.
 *
 * Auto-scroll stops the moment someone scrolls by hand. A panel that keeps
 * yanking you back to the playhead while you are reading ahead is worse than
 * one that does not follow at all.
 */
export function TranscriptView({ lines }: { lines: Line[] }) {
  const { currentTime } = usePlayerState();
  const { seek, play } = usePlayerControls();

  const containerRef = useRef<HTMLOListElement>(null);
  const followingRef = useRef(true);
  const programmaticScroll = useRef(false);

  const activeIndex = activeLine(lines, currentTime);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onScroll = () => {
      // Distinguishing a person's scroll from the one this component just
      // performed. Without the flag, following would switch itself off on the
      // first automatic scroll and never come back.
      if (programmaticScroll.current) {
        programmaticScroll.current = false;
        return;
      }
      followingRef.current = false;
    };

    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!followingRef.current || activeIndex < 0) return;

    const container = containerRef.current;
    const line = container?.querySelector<HTMLElement>(
      `[data-passage="${activeIndex}"]`,
    );
    if (!container || !line) return;

    programmaticScroll.current = true;
    container.scrollTo({
      top: line.offsetTop - container.clientHeight / 3,
      behavior: "smooth",
    });
  }, [activeIndex]);

  if (lines.length === 0) {
    return (
      <p className="py-8 text-center text-(length:--step--1) text-muted">
        This episode has no transcript yet.
      </p>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h2 className="text-(length:--step-0) font-medium">Transcript</h2>
        <button
          type="button"
          onClick={() => {
            followingRef.current = true;
            programmaticScroll.current = true;
            containerRef.current
              ?.querySelector(`[data-passage="${Math.max(0, activeIndex)}"]`)
              ?.scrollIntoView({ block: "center", behavior: "smooth" });
          }}
          className="rounded-(--radius-pill) border border-rule px-3 py-1 text-(length:--step--2) text-muted hover:border-brand hover:text-brand"
        >
          Follow along
        </button>
      </div>

      <ol
        ref={containerRef}
        className="mt-3 max-h-[60dvh] space-y-1 overflow-y-auto pr-2"
      >
        {lines.map((line, index) => (
          <li key={line.index} data-passage={index}>
            <button
              type="button"
              onClick={() => {
                seek(line.start_sec);
                void play();
              }}
              className={cn(
                "flex w-full gap-3 rounded-(--radius-sm) px-2 py-2 text-left",
                "transition-colors hover:bg-surface",
                index === activeIndex && "bg-brand-faint",
              )}
            >
              <span
                className={cn(
                  "shrink-0 font-mono text-(length:--step--2) tabular-nums",
                  index === activeIndex ? "text-brand" : "text-muted",
                )}
              >
                {formatTimecode(line.start_sec)}
              </span>
              <span
                className={cn(
                  "text-pretty text-(length:--step--1)",
                  index === activeIndex ? "text-ink" : "text-muted",
                )}
              >
                {line.text}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}
