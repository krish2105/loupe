"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

/** The platform never changes mid-session, so there is nothing to subscribe to. */
const noSubscription = () => () => {};

/**
 * The search capsule.
 *
 * Search-inside-video is the product's thesis, so it floats over the content
 * field rather than sitting in a header band — burying the thesis in chrome
 * would contradict it. The placeholder names both things it can find, because
 * "find a moment" is the capability nobody expects from a video product.
 */
export function SearchCapsule({ className }: { className?: string }) {
  const inputRef = useRef<HTMLInputElement>(null);

  // Reading navigator during render would break SSR; setting it in an effect
  // would cause a cascading render. useSyncExternalStore is the sanctioned way
  // to read a browser value that the server cannot know.
  const isMac = useSyncExternalStore(
    noSubscription,
    () => /Mac|iPhone|iPad/.test(navigator.platform),
    () => false,
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <form
      role="search"
      className={cn("w-full max-w-[620px]", className)}
      onSubmit={(event) => {
        // Search lands in Phase 2. Submitting now would navigate to a route that
        // does not exist, which is worse than doing nothing visible.
        event.preventDefault();
      }}
    >
      <label htmlFor="site-search" className="sr-only">
        Search talks and moments
      </label>

      <div
        className={cn(
          "group flex items-center gap-3 rounded-(--radius-pill)",
          "border border-rule bg-riser px-4 py-2.5",
          "transition-colors focus-within:border-dust",
        )}
      >
        <svg
          viewBox="0 0 20 20"
          aria-hidden="true"
          className="size-[17px] shrink-0 text-dust"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
        >
          <circle cx="9" cy="9" r="5.5" />
          <path d="m13.2 13.2 3.3 3.3" />
        </svg>

        <input
          id="site-search"
          ref={inputRef}
          type="search"
          autoComplete="off"
          placeholder="Find a moment, or a talk"
          className={cn(
            "min-w-0 flex-1 bg-transparent text-(length:--step-0)",
            "text-screen placeholder:text-dust",
            // The capsule itself takes the focus ring, so the input inside it
            // does not draw a second one.
            "outline-none",
          )}
        />

        <kbd
          className={cn(
            "hidden shrink-0 rounded-(--radius-sm) border border-rule",
            "px-1.5 py-0.5 font-mono text-(length:--step--2) text-dust sm:block",
          )}
        >
          {isMac ? "⌘K" : "Ctrl K"}
        </kbd>
      </div>
    </form>
  );
}
