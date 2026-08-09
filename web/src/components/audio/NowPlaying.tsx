"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/shell/Icon";
import { Avatar } from "@/components/shell/Avatar";
import { usePlayerControls, usePlayerState } from "@/components/player/PlayerContext";
import { getTranscript, type Line } from "@/lib/audio";
import { useQueueControls, useQueueState } from "./QueueContext";
import { SleepTimer } from "./SleepTimer";
import { TranscriptView } from "./TranscriptView";
import { cn, formatTimecode } from "@/lib/utils";

/**
 * The full-screen listening view, expanded from the player bar.
 *
 * In a music app this surface is dominated by artwork, because artwork is what
 * a track has. An episode here has none — shows carry an avatar and episodes
 * carry nothing — so a large square would be a placeholder occupying the best
 * space on the screen.
 *
 * The transcript takes it instead. That is not a substitute for the missing
 * artwork, it is the thing this product actually has that a music app does not:
 * the words, timed, followable, and clickable to seek. ADR 0003 argued spoken
 * audio was the right catalogue because every capability already built applies
 * to it. This is what that looks like when it is given the whole screen.
 *
 * There is no second media element here. The one in the player bar keeps
 * playing and this view reads the same store, which is the only reason
 * expanding does not interrupt the audio.
 */
export function NowPlaying({ onCollapse }: { onCollapse: () => void }) {
  const { current, state, upcoming } = useQueueState();
  const { next, previous, toggleShuffle, cycleRepeat, jumpTo } = useQueueControls();
  const { toggle, seek, nudge, setRate } = usePlayerControls();
  const { currentTime, duration, isPlaying, rate } = usePlayerState();

  // Keyed by episode rather than cleared on change. Clearing meant a
  // synchronous setState in an effect, and holding the id makes the guard
  // structural: the previous episode's transcript can never appear under the
  // new episode's title, even for one frame.
  const [transcript, setTranscript] = useState<{ id: string; lines: Line[] } | null>(
    null,
  );
  const [showQueue, setShowQueue] = useState(false);
  const collapseRef = useRef<HTMLButtonElement>(null);

  const currentId = current?.id;

  useEffect(() => {
    if (!currentId) return;

    let cancelled = false;
    void getTranscript(currentId).then((data) => {
      if (!cancelled) setTranscript({ id: currentId, lines: data?.lines ?? [] });
    });

    return () => {
      cancelled = true;
    };
  }, [currentId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCollapse();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onCollapse]);

  useEffect(() => {
    // Focus moves in, so the first Tab lands inside this view rather than
    // somewhere behind it.
    collapseRef.current?.focus();

    // The page behind is made inert rather than trapped in a hand-written focus
    // loop: `inert` removes it from the tab order and from assistive
    // technology in one attribute, which is what a focus trap is imitating.
    const shell = document.querySelector<HTMLElement>("[data-app-shell]");
    shell?.setAttribute("inert", "");
    document.documentElement.style.overflow = "hidden";

    return () => {
      shell?.removeAttribute("inert");
      document.documentElement.style.overflow = "";
    };
  }, []);

  if (!current) return null;

  const progress = duration > 0 ? currentTime / duration : 0;
  const lines = transcript?.id === current.id ? transcript.lines : [];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Now playing: ${current.title}`}
      className={cn(
        "loupe-sheet fixed inset-0 z-50 flex flex-col bg-canvas",
        "pb-[env(safe-area-inset-bottom)]",
      )}
    >
      <header className="flex items-center gap-3 border-b border-rule px-4 py-3">
        <button
          ref={collapseRef}
          type="button"
          onClick={onCollapse}
          title="Collapse"
          className="grid size-9 shrink-0 place-items-center rounded-full text-muted hover:bg-surface"
        >
          <Icon name="collapse" className="size-5" />
          <span className="sr-only">Collapse the player</span>
        </button>

        <p className="min-w-0 flex-1 truncate text-center text-(length:--step--2) uppercase tracking-wide text-muted">
          {current.channelName}
        </p>

        <button
          type="button"
          onClick={() => setShowQueue((open) => !open)}
          title={`Queue, ${upcoming.length} up next`}
          className={cn(
            "grid size-9 shrink-0 place-items-center rounded-full hover:bg-surface",
            showQueue ? "text-brand" : "text-muted",
          )}
        >
          <Icon name="queue" className="size-5" />
          <span className="sr-only">Queue, {upcoming.length} up next</span>
        </button>
      </header>

      <div className="mx-auto flex w-full max-w-[720px] min-h-0 flex-1 flex-col px-4">
        <div className="flex items-center gap-4 pt-6">
          <Avatar name={current.channelName} size={64} />
          <div className="min-w-0">
            <h1 className="text-pretty text-(length:--step-2) font-medium">
              <Link href={`/listen/${current.id}`} onClick={onCollapse} className="hover:underline">
                {current.title}
              </Link>
            </h1>
            <Link
              href={`/c/${current.channelHandle}`}
              onClick={onCollapse}
              className="text-(length:--step--1) text-muted hover:underline"
            >
              {current.channelName}
            </Link>
          </div>
        </div>

        <div className="pt-6">
          <label className="sr-only" htmlFor="now-playing-scrubber">
            Position in {current.title}
          </label>
          <input
            id="now-playing-scrubber"
            type="range"
            min={0}
            max={duration || 0}
            step={1}
            value={currentTime}
            onChange={(event) => seek(Number(event.target.value))}
            className="loupe-scrubber block h-1.5 w-full cursor-pointer rounded-(--radius-pill)"
            style={{ ["--progress" as string]: `${progress * 100}%` }}
          />
          <div className="mt-2 flex justify-between font-mono text-(length:--step--2) text-muted tabular-nums">
            <span>{formatTimecode(currentTime)}</span>
            {/* Time left, not total. Mid-episode the useful question is how much
                is left, and the total is already on the card that started it. */}
            <span>−{formatTimecode(Math.max(0, duration - currentTime))}</span>
          </div>
        </div>

        <div className="flex items-center justify-center gap-2 pt-5">
          <Control label={state.shuffle ? "Shuffle on" : "Shuffle off"} onClick={toggleShuffle} active={state.shuffle}>
            <Icon name="shuffle" className="size-5" />
          </Control>
          <Control label="Previous" onClick={previous}>
            <Icon name="previous" className="size-6" />
          </Control>
          <Control label="Back 15 seconds" onClick={() => nudge(-15)}>
            <Icon name="rewind" className="size-6" />
          </Control>

          <button
            type="button"
            onClick={toggle}
            title={isPlaying ? "Pause" : "Play"}
            className="grid size-14 shrink-0 place-items-center rounded-full bg-brand text-white transition-opacity hover:opacity-90"
          >
            <Icon name={isPlaying ? "pause" : "play"} className="size-7" />
            <span className="sr-only">{isPlaying ? "Pause" : "Play"}</span>
          </button>

          <Control label="Forward 30 seconds" onClick={() => nudge(30)}>
            <Icon name="forward" className="size-6" />
          </Control>
          <Control label="Next" onClick={next}>
            <Icon name="next" className="size-6" />
          </Control>
          <Control
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
            <Icon name={state.repeat === "one" ? "repeat-one" : "repeat"} className="size-5" />
          </Control>
        </div>

        <div className="flex items-center justify-center gap-3 pt-4">
          <label className="sr-only" htmlFor="now-playing-speed">
            Playback speed
          </label>
          <select
            id="now-playing-speed"
            value={rate}
            onChange={(event) => setRate(Number(event.target.value))}
            className="rounded-(--radius-sm) border border-rule bg-canvas px-2 py-1 text-(length:--step--2)"
          >
            {[0.75, 1, 1.25, 1.5, 1.75, 2].map((option) => (
              <option key={option} value={option}>
                {option}×
              </option>
            ))}
          </select>

          <SleepTimer />
        </div>

        <div className="min-h-0 flex-1 overflow-hidden pb-6 pt-6">
          {showQueue ? (
            <section aria-label="Queue" className="h-full overflow-y-auto">
              <h2 className="text-(length:--step--1) font-medium text-muted">Up next</h2>
              {upcoming.length === 0 ? (
                <p className="py-8 text-center text-(length:--step--2) text-muted">
                  Nothing queued after this one.
                </p>
              ) : (
                <ol className="mt-3 divide-y divide-rule border-y border-rule">
                  {upcoming.map((track, index) => (
                    <li key={`${track.id}-${index}`}>
                      <button
                        type="button"
                        onClick={() => jumpTo(state.cursor + 1 + index)}
                        className="w-full py-3 text-left"
                      >
                        <span className="block truncate text-(length:--step--1)">
                          {track.title}
                        </span>
                        <span className="block truncate text-(length:--step--2) text-muted">
                          {track.channelName}
                        </span>
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          ) : (
            <TranscriptView lines={lines} fill />
          )}
        </div>
      </div>
    </div>
  );
}

function Control({
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
        "grid size-11 shrink-0 place-items-center rounded-full transition-colors",
        "hover:bg-surface",
        active ? "text-brand" : "text-muted",
      )}
    >
      {children}
      <span className="sr-only">{label}</span>
    </button>
  );
}
