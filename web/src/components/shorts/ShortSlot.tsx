"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Avatar } from "@/components/shell/Avatar";
import { Icon } from "@/components/shell/Icon";
import { MarkNode } from "@/components/mark/Mark";
import { useHls } from "@/components/player/useHls";
import type { VideoSummary } from "@/lib/catalogue";
import type { SlotPlan } from "./window-policy";
import { cn, formatViews } from "@/lib/utils";

/**
 * One item in the vertical feed.
 *
 * Deliberately does not use the shared player store. That store is a *single*
 * source of playback truth — exactly right for the video page, where one
 * player exists and the AI panel seeks it. A feed has up to seven elements and
 * needs no external seek, so routing them all through one store would mean
 * inventing a multiplexer for a problem this surface does not have.
 *
 * What it does share is `useHls`, so adaptive bitrate and the Safari native
 * path behave identically here.
 */

export type Short = VideoSummary & { hls_url: string | null };

export function ShortSlot({
  short,
  plan,
  reduceMotion,
}: {
  short: Short;
  plan: SlotPlan;
  reduceMotion: boolean;
}) {
  const containerRef = useRef<HTMLElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [mounted, setMounted] = useState(false);
  const [muted, setMuted] = useState(true);
  const [canPlay, setCanPlay] = useState(false);

  const setVideo = useCallback((element: HTMLVideoElement | null) => {
    videoRef.current = element;
    setMounted(element !== null);
  }, []);

  // Only the loading slots attach a source at all. This is where the window
  // policy stops being a plan and starts being bandwidth.
  const source = plan.preload === "auto" ? short.hls_url : null;
  useHls(videoRef, source, mounted);

  // Readiness has to be state, not a ref: the play effect below must re-run
  // when the source finally attaches. Without this the first play() call
  // races useHls, rejects, and nothing ever retries it.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onReady = () => setCanPlay(true);
    video.addEventListener("loadeddata", onReady);
    video.addEventListener("canplay", onReady);
    if (video.readyState >= 2) setCanPlay(true);

    return () => {
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("canplay", onReady);
    };
  }, [mounted, source]);

  // Play only the active item.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (plan.playing) {
      const started = video.play();
      // Rejects with AbortError whenever a scroll interrupts it, which is
      // constant in a feed.
      if (started && typeof started.catch === "function") started.catch(() => {});
    } else {
      video.pause();
      // Rewind so returning to an item restarts it rather than resuming three
      // seconds from its end.
      if (video.currentTime > 0) video.currentTime = 0;
    }
  }, [plan.playing, mounted, canPlay]);

  return (
    <article
      ref={containerRef}
      className={cn(
        "relative flex h-[100svh] snap-start snap-always items-center justify-center",
        "sm:h-[calc(100svh-var(--topbar-height))]",
      )}
    >
      <div
        className={cn(
          "relative h-full w-full overflow-hidden bg-black sm:h-[min(88svh,900px)]",
          "sm:aspect-[9/16] sm:w-auto sm:rounded-(--radius-md)",
          // §7.4: momentum that settles rather than snapping hard. The browser
          // owns the snap; this is the settle — transform only, so it composites.
          "transition-transform duration-500 [transition-timing-function:var(--ease-spring)]",
          !reduceMotion && (plan.playing ? "scale-100" : "scale-[0.965]"),
        )}
      >
        {plan.mounted ? (
          <video
            ref={setVideo}
            playsInline
            loop
            muted={muted}
            preload={plan.preload}
            aria-label={short.title}
            className="size-full object-cover"
          />
        ) : (
          // Beyond ±3 there is no element at all — the placeholder keeps the
          // scroll height stable so destroying one does not move the page.
          <div className="size-full bg-surface" />
        )}

        <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/75 via-transparent to-black/25" />

        <button
          type="button"
          onClick={() => setMuted((value) => !value)}
          aria-label={muted ? "Unmute" : "Mute"}
          className="absolute right-3 top-3 grid size-10 place-items-center rounded-full bg-black/50 text-white"
        >
          <Icon name={muted ? "muted" : "volume"} className="size-5" />
          <span className="sr-only">{muted ? "Unmute" : "Mute"}</span>
        </button>

        <div className="absolute inset-x-0 bottom-0 p-4 pb-8">
          <div className="flex items-center gap-2">
            <Avatar name={short.channel.name} size={32} />
            <Link
              href={`/c/${short.channel.handle}`}
              className="text-(length:--step--1) font-medium text-white"
            >
              {short.channel.name}
            </Link>
          </div>

          <h2 className="mt-2 text-pretty text-(length:--step-0) font-medium text-white">
            <Link href={`/watch/${short.id}`}>{short.title}</Link>
          </h2>

          <p className="mt-1 flex items-center gap-2 text-(length:--step--2) text-white/70">
            {formatViews(short.view_count)}
            {short.capabilities.askable && (
              <>
                <span aria-hidden="true">·</span>
                <MarkNode />
                Searchable inside
              </>
            )}
          </p>
        </div>
      </div>
    </article>
  );
}
