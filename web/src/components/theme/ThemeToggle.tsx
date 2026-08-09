"use client";

import { cn } from "@/lib/utils";

/**
 * Switches between the two themes.
 *
 * Both are designed, not derived: dark's referent is a warm room, light's is a
 * cool lit surface.
 *
 * Deliberately stateless. The current theme already lives on the root element
 * as `data-theme`, so the glyph is driven by CSS rather than mirrored into
 * React state — which avoids a hydration mismatch and a cascading render on
 * mount, and means the control is correct on the very first paint.
 */
export function ThemeToggle({ className }: { className?: string }) {
  function toggle() {
    const root = document.documentElement;
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";

    // Animating colour across the whole tree is the one thing guaranteed to
    // drop frames on a mid-range device (§7.3), so transitions are suppressed
    // for the single frame the swap takes.
    root.classList.add("theme-swapping");
    root.setAttribute("data-theme", next);
    try {
      localStorage.setItem("loupe-theme", next);
    } catch {
      // Private browsing denies storage. The theme still applies for this
      // session, which is the part the person actually asked for.
    }
    requestAnimationFrame(() => root.classList.remove("theme-swapping"));
  }

  return (
    <button
      type="button"
      onClick={toggle}
      // States what the control does, not which theme is currently on — the
      // glyph carries that, and a label that changes under you is worse.
      aria-label="Switch between light and dark"
      title="Switch between light and dark"
      className={cn(
        "grid size-9 place-items-center rounded-(--radius-sm)",
        "text-muted transition-colors hover:text-ink",
        className,
      )}
    >
      {/* A lens that fills as the room darkens. */}
      <svg viewBox="0 0 20 20" aria-hidden="true" className="size-[18px]" fill="none">
        <circle cx="10" cy="10" r="6.25" stroke="currentColor" strokeWidth="1.5" />
        <path
          d="M10 3.75a6.25 6.25 0 0 0 0 12.5z"
          fill="currentColor"
          className="hidden dark:block"
        />
      </svg>
    </button>
  );
}
