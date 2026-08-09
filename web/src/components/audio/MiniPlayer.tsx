"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/shell/Icon";
import { useHls } from "@/components/player/useHls";
import { usePlayerControls, usePlayerState } from "@/components/player/PlayerContext";
import { useProgressReporting } from "@/components/player/useProgressReporting";
import { useQueueControls, useQueueState, useQueueStore } from "./QueueContext";
import { QueuePanel } from "./QueuePanel";
import { SleepTimer } from "./SleepTimer";
import { useMediaSession } from "./useMediaSession";
import { usePlayhead } from "./usePlayhead";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * The persistent player bar (ADR 0003).
 *
 * This is the component the week-1 player abstraction was for. §5.1 asked for a
 * framework-free store built before anything consumed it, on the argument that
 * retrofitting one later turns citation-seek into prop drilling. The payment
 * arrives here instead: the media element moves from inside the video page to
 * inside a bar in the root layout, and nothing that reads playback state had to
 * change, because none of it ever knew where the element lived.
 *
 * The element is a <video> rather than an <audio>. HLS needs Media Source
 * Extensions and hls.js attaches to a video element in every browser; an audio
 * element gets you native HLS on Safari and silence everywhere else. It renders
 * at zero size, which is the standard way to do this and is not a workaround
 * for anything.
 */

const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];

export function MiniPlayer() {
  const { current, state, upcoming } = useQueueState();
  const { next, previous, toggleShuffle, cycleRepeat } = useQueueControls();
  const queueStore = useQueueStore();

  const mediaRef = useRef<HTMLVideoElement | null>(null);
  const [mounted, setMounted] = useState(false);
  const [queueOpen, setQueueOpen] = useState(false);
  const [speed, setSpeed] = useState(1);

  const setMedia = useCallback((element: HTMLVideoElement | null) => {
    mediaRef.current = element;
    setMounted(element !== null);
  }, []);

  const { attach, toggle, seek, nudge } = usePlayerControls();
  const { currentTime, duration, isPlaying } = usePlayerState();

  useHls(mediaRef, current?.src ?? "", mounted && Boolean(current));
  useProgressReporting(current?.id ?? null);
  usePlayhead(queueStore, current?.id ?? null);
  useMediaSession();

  useEffect(() => attach(mediaRef.current), [attach, mounted, current?.id]);

  /*
    Room for the bar.

    Set on the document element rather than passed through the shell, because
    every page would otherwise have to remember it and the one that forgot would
    have its last row permanently covered. This is DOM outside React's tree, so
    writing to it directly is the honest way round.
  */
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("has-miniplayer");
    return () => root.classList.remove("has-miniplayer");
  }, []);

  // Playback speed is applied to the element rather than held in the store,
  // because it changes nothing the store models. Re-applied on track change
  // since a new source resets it.
  useEffect(() => {
    if (mediaRef.current) mediaRef.current.playbackRate = speed;
  }, [speed, current?.id]);


  if (!current) return null;

  const progress = duration > 0 ? currentTime / duration : 0;

  return (
    <>
      {/* Zero-sized on purpose: see the note above about HLS and audio elements. */}
      <video
        ref={setMedia}
        className="pointer-events-none absolute size-0"
        playsInline
        preload="metadata"
        aria-hidden="true"
      />

      {queueOpen && <QueuePanel onClose={() => setQueueOpen(false)} />}

      <div
        className={cn(
          "fixed inset-x-0 bottom-0 z-40 border-t border-rule bg-canvas",
          "pb-[env(safe-area-inset-bottom)]",
        )}
        style={{ minHeight: "var(--miniplayer-height)" }}
      >
        {/* A seekable bar rather than a decorative one: on a forty-minute
            episode, being unable to scrub from the bar means opening the
            episode page to move thirty seconds. */}
        <label className="sr-only" htmlFor="mini-scrubber">
          Position in {current.title}
        </label>
        <input
          id="mini-scrubber"
          type="range"
          min={0}
          max={duration || 0}
          step={1}
          value={currentTime}
          onChange={(event) => seek(Number(event.target.value))}
          className="loupe-scrubber block h-1 w-full cursor-pointer"
          style={{ ["--progress" as string]: `${progress * 100}%` }}
        />

        <div className="flex items-center gap-3 px-3 py-2 md:px-4">
          <div className="min-w-0 flex-1">
            <Link
              href={`/listen/${current.id}`}
              className="block truncate text-(length:--step--1) font-medium hover:underline"
            >
              {current.title}
            </Link>
            <Link
              href={`/c/${current.channelHandle}`}
              className="block truncate text-(length:--step--2) text-muted hover:underline"
            >
              {current.channelName}
            </Link>
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <IconButton
              label={state.shuffle ? "Shuffle on" : "Shuffle off"}
              onClick={toggleShuffle}
              active={state.shuffle}
            >
              <Icon name="shuffle" className="size-5" />
            </IconButton>

            <IconButton label="Previous" onClick={previous}>
              <Icon name="previous" className="size-5" />
            </IconButton>

            <IconButton label="Back 15 seconds" onClick={() => nudge(-15)}>
              <Icon name="rewind" className="size-5" />
            </IconButton>

            <button
              type="button"
              onClick={toggle}
              title={isPlaying ? "Pause" : "Play"}
              className="grid size-10 shrink-0 place-items-center rounded-full bg-brand text-white"
            >
              <Icon name={isPlaying ? "pause" : "play"} className="size-5" />
              <span className="sr-only">{isPlaying ? "Pause" : "Play"}</span>
            </button>

            <IconButton label="Forward 30 seconds" onClick={() => nudge(30)}>
              <Icon name="forward" className="size-5" />
            </IconButton>

            <IconButton label="Next" onClick={next}>
              <Icon name="next" className="size-5" />
            </IconButton>

            <IconButton
              label={
                state.repeat === "one"
                  ? "Repeat this episode"
                  : state.repeat === "all"
                    ? "Repeat queue"
                    : "Repeat off"
              }
              onClick={cycleRepeat}
              active={state.repeat !== "off"}
            >
              <Icon
                name={state.repeat === "one" ? "repeat-one" : "repeat"}
                className="size-5"
              />
            </IconButton>
          </div>

          <div className="hidden shrink-0 items-center gap-3 md:flex">
            <span className="font-mono text-(length:--step--2) text-muted tabular-nums">
              {formatTimecode(currentTime)} / {formatTimecode(duration)}
            </span>

            <label className="sr-only" htmlFor="mini-speed">
              Playback speed
            </label>
            <select
              id="mini-speed"
              value={speed}
              onChange={(event) => setSpeed(Number(event.target.value))}
              className="rounded-(--radius-sm) border border-rule bg-canvas px-2 py-1 text-(length:--step--2)"
            >
              {SPEEDS.map((option) => (
                <option key={option} value={option}>
                  {option}×
                </option>
              ))}
            </select>
          </div>

          <SleepTimer />

          <IconButton
            label={`Queue, ${upcoming.length} up next`}
            onClick={() => setQueueOpen((open) => !open)}
            active={queueOpen}
          >
            <Icon name="queue" className="size-5" />
          </IconButton>
        </div>
      </div>
    </>
  );
}

function IconButton({
  label,
  onClick,
  active = false,
  children,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={cn(
        "grid size-9 shrink-0 place-items-center rounded-full transition-colors",
        "hover:bg-surface",
        active ? "text-brand" : "text-muted",
      )}
    >
      {children}
      <span className="sr-only">{label}</span>
    </button>
  );
}
