"use client";

import { useEffect, useState, type RefObject } from "react";

/**
 * Attaches an HLS source to a media element.
 *
 * §9.1: adaptive bitrate from the manifest, never forcing a resolution. hls.js
 * defaults to automatic level selection and this deliberately leaves it there —
 * pinning a level is the most common way a custom player quietly becomes worse
 * than the default one.
 *
 * Safari plays HLS natively and hls.js explicitly should not be used there.
 *
 * Takes a ref rather than the element itself: attaching a stream mutates the
 * element, and a DOM node held in state is a value React expects nobody to
 * modify. `mounted` exists only to re-run the effect once the ref is populated.
 */

export type HlsStatus = "idle" | "loading" | "ready" | "error";

type Outcome = { src: string; status: "ready" | "error" };
type Level = { src: string; label: string };

export function useHls(
  videoRef: RefObject<HTMLVideoElement | null>,
  src: string | null,
  mounted: boolean,
): { status: HlsStatus; level: string | null } {
  // Both pieces of state carry the src they belong to, so a source change
  // reports "loading" by derivation rather than by resetting state inside the
  // effect — a synchronous setState there would cascade an extra render.
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [level, setLevel] = useState<Level | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !src || !mounted) return;

    // Native HLS — Safari and iOS. Assigning src is the whole integration.
    if (video.canPlayType("application/vnd.apple.mpegurl")) {
      const onReady = () => setOutcome({ src, status: "ready" });
      const onError = () => setOutcome({ src, status: "error" });

      video.addEventListener("loadedmetadata", onReady, { once: true });
      video.addEventListener("error", onError, { once: true });
      video.src = src;

      return () => {
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

      hls.on(Hls.Events.MANIFEST_PARSED, () =>
        setOutcome({ src, status: "ready" }),
      );

      hls.on(Hls.Events.LEVEL_SWITCHED, (_event, data) => {
        const current = hls.levels[data.level];
        if (current) setLevel({ src, label: `${current.height}p` });
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
      cancelled = true;
      instance?.destroy();
    };
  }, [videoRef, src, mounted]);

  const status: HlsStatus = !src
    ? "idle"
    : outcome?.src === src
      ? outcome.status
      : "loading";

  return { status, level: level?.src === src ? level.label : null };
}
