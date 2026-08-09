"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useReducedMotion } from "motion/react";
import { ShortSlot, type Short } from "./ShortSlot";
import { activeIndexFromScroll, concurrentLoads, planWindow } from "./window-policy";
import { cn } from "@/lib/utils";

/**
 * The vertical feed — §13.
 *
 * CSS scroll-snap owns the scrolling. That is deliberate: a JavaScript-driven
 * feed has to re-implement momentum, rubber-banding, and interruption, and it
 * will be worse than the compositor's on exactly the mid-range hardware §15
 * flags as the risk. The browser scrolls; this component only decides which
 * item is active and what the window policy says to do about it.
 */
export function ShortsFeed({ shorts }: { shorts: Short[] }) {
  const [activeIndex, setActiveIndex] = useState(0);
  const trackRef = useRef<HTMLDivElement | null>(null);
  const reduce = useReducedMotion() ?? false;

  const plans = useMemo(
    () => planWindow(activeIndex, shorts.length),
    [activeIndex, shorts.length],
  );

  // The invariant §13 is really asking for, checked where it can still be
  // fixed. In production this compiles away; in development it turns a subtle
  // bandwidth regression into a console error naming the cause.
  if (process.env.NODE_ENV !== "production") {
    const loading = concurrentLoads(plans);
    if (loading > 3) {
      console.error(
        `Shorts window policy violated: ${loading} elements loading at once. ` +
          "§13 allows the active item plus two ahead.",
      );
    }
  }

  // Active slot from scroll position, throttled to one computation per frame.
  //
  // §13 specifies an intersection observer; window-policy.ts records why this
  // deviates. The listener is passive so it never blocks scrolling, and the
  // work inside it is one division and a clamp.
  useEffect(() => {
    const track = trackRef.current;
    if (!track || shorts.length === 0) return;

    let frame = 0;

    const measure = () => {
      frame = 0;
      const slotHeight = track.clientHeight;
      const next = activeIndexFromScroll(track.scrollTop, slotHeight, shorts.length);
      setActiveIndex((current) => (current === next ? current : next));
    };

    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(measure);
    };

    measure();
    track.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      if (frame) cancelAnimationFrame(frame);
      track.removeEventListener("scroll", onScroll);
    };
  }, [shorts.length]);

  if (shorts.length === 0) {
    return (
      <div className="mx-auto max-w-[46ch] py-24 text-center">
        <p className="text-(length:--step-1)">No shorts yet</p>
        <p className="mt-2 text-pretty text-(length:--step--1) text-muted">
          Short talks appear here as a vertical feed.
        </p>
      </div>
    );
  }

  return (
    <div
      ref={trackRef}
      className={cn(
        // `mandatory` rather than `proximity`: a feed that sometimes leaves an
        // item half-scrolled reads as broken. The settle §7.4 asks for is the
        // scale transition on the slot, not a looser snap.
        "h-[100svh] snap-y snap-mandatory overflow-y-auto overscroll-y-contain",
        "no-scrollbar -mx-4 md:-mx-6",
        "sm:h-[calc(100svh-var(--topbar-height))]",
      )}
    >
      {shorts.map((short, index) => (
        <ShortSlot
          key={short.id}
          short={short}
          plan={plans[index]!}
          reduceMotion={reduce}
        />
      ))}
    </div>
  );
}
