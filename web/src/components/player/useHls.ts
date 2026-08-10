"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import {
  AUTO,
  qualityOptions,
  type QualityLevel,
  type QualityOption,
} from "./quality-options";

/**
 * Attaches an HLS source to a media element.
 *
 * §9.1: adaptive bitrate from the manifest. Auto is the default and stays the
 * default — pinning a level by default is the most common way a custom player
 * quietly becomes worse than the stock one.
 *
 * It does not stay the *only* option, which is where this originally went
 * wrong. The controls rendered the resolution ABR had chosen as a label that
 * looked exactly like the quality button of every player people already use,
 * and clicking it did nothing. An affordance that cannot be operated is worse
 * than no affordance. A viewer on a metered connection also has a reason to
 * pin 360p that the algorithm has no way to know.
 *
 * Safari plays HLS natively and hls.js explicitly should not be used there.
 * Native playback exposes no level API, so quality selection is unavailable —
 * `options` comes back empty and the control does not render at all, rather
 * than rendering something inert.
 *
 * Takes a ref rather than the element itself: attaching a stream mutates the
 * element, and a DOM node held in state is a value React expects nobody to
 * modify. `mounted` exists only to re-run the effect once the ref is populated.
 */

export type HlsStatus = "idle" | "loading" | "ready" | "error";

/**
 * How long nothing may happen before a load is called dead.
 *
 * Sized for a sleeping free-tier instance, which can take the better part of a
 * minute to answer its first request. The clock resets on any activity, so this
 * bounds *silence* rather than total load time.
 */
const STALL_MS = 45_000;

export type HlsQuality = {
  /** Menu rows. Empty when there is no choice to offer. */
  options: QualityOption[];
  /** The selected level index; `AUTO` (-1) unless pinned. */
  selected: number;
  /** The height actually playing, whoever chose it. */
  activeHeight: number | null;
  select: (index: number) => void;
};

type Outcome = { src: string; status: "ready" | "error" };
type Level = { src: string; height: number };

export function useHls(
  videoRef: RefObject<HTMLVideoElement | null>,
  src: string | null,
  mounted: boolean,
): { status: HlsStatus; level: string | null; quality: HlsQuality } {
  // Both pieces of state carry the src they belong to, so a source change
  // reports "loading" by derivation rather than by resetting state inside the
  // effect — a synchronous setState there would cascade an extra render.
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [level, setLevel] = useState<Level | null>(null);
  const [options, setOptions] = useState<QualityOption[]>([]);
  const [selected, setSelected] = useState<number>(AUTO);

  // The live hls.js instance, for the setter. A ref rather than state: nothing
  // renders from it, and putting it in state would re-render the whole player
  // once per source change for no visible reason.
  const hlsRef = useRef<import("hls.js").default | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !src || !mounted) return;

    /**
     * A stream that never loads has to become an error eventually — but only
     * one that never loads, not one that is merely slow.
     *
     * The first version of this was a flat twenty-second timeout, and it was
     * wrong in a way worth recording. The media service runs on an instance
     * that sleeps when idle and can take the better part of a minute to wake,
     * so the timeout fired on a load that was working, latched, and turned a
     * slow start into a permanent failure message. That is a worse bug than
     * the silence it replaced: the black player at least recovered.
     *
     * So the clock is reset by any sign of life. `progress` fires as bytes
     * arrive on the native path; hls.js fires its own events well before a
     * manifest is parsed. A load that is moving is never failed, and a load
     * that is genuinely dead still is.
     */
    let stall: ReturnType<typeof setTimeout>;

    const fail = () =>
      setOutcome((current) =>
        current?.src === src ? current : { src, status: "error" },
      );

    const waitAgain = () => {
      clearTimeout(stall);
      stall = setTimeout(fail, STALL_MS);
    };

    waitAgain();
    video.addEventListener("progress", waitAgain);
    video.addEventListener("loadstart", waitAgain);

    // Native HLS — Safari and iOS. Assigning src is the whole integration.
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      const onReady = () => setOutcome({ src, status: "ready" });
      const onError = () => setOutcome({ src, status: "error" });

      video.addEventListener("loadedmetadata", onReady, { once: true });
      video.addEventListener("error", onError, { once: true });
      video.src = src;

      return () => {
        clearTimeout(stall);
        video.removeEventListener("progress", waitAgain);
        video.removeEventListener("loadstart", waitAgain);
        video.removeEventListener("loadedmetadata", onReady);
        video.removeEventListener("error", onError);
        video.removeAttribute("src");
        video.load();
      };
    }

    let cancelled = false;
    let instance: import("hls.js").default | null = null;

    // Dynamically imported so hls.js stays out of the bundle for every page
    // that is not a video page — which is most of them.
    void import("hls.js").then(({ default: Hls }) => {
      if (cancelled) return;

      if (!Hls.isSupported()) {
        setOutcome({ src, status: "error" });
        return;
      }

      const hls = new Hls({
        // -1 is "let ABR choose", which is the point.
        startLevel: -1,
        capLevelToPlayerSize: true,
      });
      instance = hls;
      hlsRef.current = hls;

      // Any hls.js activity counts as progress, so a slow first fetch of the
      // manifest does not trip the stall clock.
      hls.on(Hls.Events.MANIFEST_LOADING, waitAgain);
      hls.on(Hls.Events.MANIFEST_LOADED, waitAgain);
      hls.on(Hls.Events.FRAG_LOADED, waitAgain);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setOutcome({ src, status: "ready" });
        const levels: QualityLevel[] = hls.levels.map((entry, index) => ({
          index,
          height: entry.height,
          bitrate: entry.bitrate,
        }));
        setOptions(qualityOptions(levels));
        setSelected(AUTO);
      });

      hls.on(Hls.Events.LEVEL_SWITCHED, (_event, data) => {
        const current = hls.levels[data.level];
        if (current) setLevel({ src, height: current.height });
      });

      hls.on(Hls.Events.ERROR, (_event, data) => {
        // Non-fatal errors are routine on a live network and hls.js recovers
        // from them itself. Surfacing them would make a working player look
        // broken.
        if (data.fatal) setOutcome({ src, status: "error" });
      });

      hls.loadSource(src);
      hls.attachMedia(video);
    });

    return () => {
      clearTimeout(stall);
      video.removeEventListener("progress", waitAgain);
      video.removeEventListener("loadstart", waitAgain);
      cancelled = true;
      instance?.destroy();
      hlsRef.current = null;
      setOptions([]);
      setSelected(AUTO);
    };
  }, [videoRef, src, mounted]);

  const select = useCallback((index: number) => {
    const hls = hlsRef.current;
    if (!hls) return;

    /**
     * One assignment is the whole integration, and the obvious second one is a
     * mistake. `capLevelToPlayerSize` holds playback to what the element can
     * actually display, so lifting that cap looks necessary before 1080p can be
     * pinned in a half-width window. It is not: capping gates only automatic
     * selection — hls.js treats `autoLevelEnabled` as `manualLevel === -1` — and
     * CapLevelController rewrites `autoLevelCapping` on every resize tick, so
     * setting it here would be overwritten within the second regardless.
     */
    hls.currentLevel = index;
    setSelected(index);
  }, []);

  const status: HlsStatus = !src
    ? "idle"
    : outcome?.src === src
      ? outcome.status
      : "loading";

  const activeHeight = level?.src === src ? level.height : null;

  return {
    status,
    level: activeHeight ? `${activeHeight}p` : null,
    quality: { options, selected, activeHeight, select },
  };
}
