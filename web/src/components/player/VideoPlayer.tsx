"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PlayerControls } from "./PlayerControls";
import { usePlayerControls, usePlayerState } from "./PlayerContext";
import type { Chapter } from "./Scrubber";
import { isTypingTarget, keyToAction } from "./keyboard";
import { useHls } from "./useHls";
import { useProgressReporting } from "./useProgressReporting";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * The custom player (§9.1).
 *
 * Owns no playback state of its own — everything routes through the player
 * store, which is what lets the AI panel seek it in Phase 6 without this
 * component knowing the panel exists.
 */

export function VideoPlayer({
  src,
  poster,
  title,
  chapters,
  resumeAtSec,
  videoId = null,
}: {
  src: string;
  poster?: string;
  title: string;
  chapters?: Chapter[];
  /** A prior position, if one is worth offering. Computed server-side. */
  resumeAtSec?: number;
  /** Omit for content with no history to keep — the demo route, or a preview. */
  videoId?: string | null;
}) {
  // The element lives in a ref because attaching a stream mutates it. `mounted`
  // is what actually re-runs the effects once the ref is populated.
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [mounted, setMounted] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const setVideo = useCallback((element: HTMLVideoElement | null) => {
    videoRef.current = element;
    setMounted(element !== null);
  }, []);

  const { attach, seek, toggle, nudge } = usePlayerControls();
  const { duration, isReady } = usePlayerState();
  const { status, level } = useHls(videoRef, src, mounted);

  // §9.1 progress writes. Subscribes imperatively, so this costs no renders.
  useProgressReporting(videoId);

  const [resumeOffer, setResumeOffer] = useState<number | null>(
    resumeAtSec && resumeAtSec > 10 ? resumeAtSec : null,
  );

  // Bind the element to the store.
  useEffect(() => attach(videoRef.current), [attach, mounted]);

  const toggleFullscreen = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void container.requestFullscreen();
  }, []);

  // §9.1 keyboard. Bound at document level so the shortcuts work without
  // having to focus the player first, but never while someone is typing.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTypingTarget(event.target)) return;

      const action = keyToAction(event);
      if (!action) return;
      event.preventDefault();

      switch (action.type) {
        case "toggle":
          toggle();
          break;
        case "nudge":
          nudge(action.seconds);
          break;
        case "seekFraction":
          if (duration > 0) seek(action.fraction * duration);
          break;
        case "volume": {
          const element = videoRef.current;
          if (element) {
            element.volume = Math.min(
              1,
              Math.max(0, element.volume + action.delta),
            );
          }
          break;
        }
        case "mute": {
          const element = videoRef.current;
          if (element) element.muted = !element.muted;
          break;
        }
        case "fullscreen":
          toggleFullscreen();
          break;
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [duration, nudge, seek, toggle, toggleFullscreen]);

  return (
    <div
      ref={containerRef}
      className="relative aspect-video w-full overflow-hidden rounded-(--radius-md) bg-black"
    >
      <video
        ref={setVideo}
        poster={poster}
        playsInline
        className="size-full"
        // Real captions arrive with the transcript in Phase 5.
        aria-label={title}
      />

      {status === "error" && (
        <div className="absolute inset-0 grid place-content-center px-6 text-center">
          <p className="text-(length:--step-0) text-ink">
            This talk will not play in your browser.
          </p>
          <p className="mt-2 text-(length:--step--1) text-muted">
            The stream could not be loaded. Try reloading, or open it in a
            different browser.
          </p>
        </div>
      )}

      {/* §9.1: resume with a dismissible notice, never silently. */}
      {resumeOffer !== null && isReady && (
        // z-20 puts it above the controls, whose gradient would otherwise wash
        // the notice out — which it did until this was set.
        <div className="absolute bottom-20 left-3 z-20 flex items-center gap-3 rounded-(--radius-md) border border-rule bg-surface px-3 py-2">
          <p className="text-(length:--step--1) text-ink">
            Pick up at {formatTimecode(resumeOffer)}?
          </p>
          <button
            type="button"
            onClick={() => {
              seek(resumeOffer);
              setResumeOffer(null);
            }}
            className={cn(
              "rounded-(--radius-sm) bg-ink px-2.5 py-1",
              "text-(length:--step--2) font-medium text-canvas",
            )}
          >
            Resume
          </button>
          <button
            type="button"
            onClick={() => setResumeOffer(null)}
            aria-label="Start from the beginning"
            className="text-(length:--step--2) text-muted hover:text-ink"
          >
            Start over
          </button>
        </div>
      )}

      <PlayerControls
        chapters={chapters}
        level={level}
        onFullscreen={toggleFullscreen}
      />
    </div>
  );
}
