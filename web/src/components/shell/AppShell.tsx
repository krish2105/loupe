"use client";

import { useCallback, useState, useSyncExternalStore } from "react";
import { Sidebar, type SidebarChannel } from "./Sidebar";
import { TopBar } from "./TopBar";
import { cn } from "@/lib/utils";

/**
 * The app frame — top bar, sidebar, content.
 *
 * Per ADR 0002 this follows the mainstream video-platform arrangement rather
 * than the icon rail the plan originally specified.
 *
 * The sidebar defaults open on large screens and closed below, but a person's
 * explicit toggle wins over the breakpoint for the rest of the session. That
 * is why `open` is a media query with an override on top rather than a piece
 * of state seeded in an effect — seeding in an effect causes a cascading
 * render and a visible jump on first paint.
 */

export type ShellUser = { email: string; initial: string };

const LARGE_SCREEN = "(min-width: 1024px)";

function subscribeToBreakpoint(callback: () => void) {
  const query = window.matchMedia(LARGE_SCREEN);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

export function AppShell({
  children,
  user = null,
  channels = [],
}: {
  children: React.ReactNode;
  user?: ShellUser | null;
  channels?: SidebarChannel[];
}) {
  const isLarge = useSyncExternalStore(
    subscribeToBreakpoint,
    () => window.matchMedia(LARGE_SCREEN).matches,
    () => true, // The server renders the desktop arrangement.
  );

  const [override, setOverride] = useState<boolean | null>(null);
  const open = override ?? isLarge;

  const toggle = useCallback(() => setOverride(!open), [open]);
  const close = useCallback(() => setOverride(false), []);

  return (
    <div className="min-h-dvh">
      <TopBar onToggleSidebar={toggle} user={user} />

      <Sidebar open={open} channels={channels} isSignedIn={Boolean(user)} />

      {/*
        Scrim — only where the sidebar is a drawer over the content.

        Always mounted and faded with CSS rather than mounted through
        AnimatePresence. The Motion version stayed on screen after `open` went
        false, the same way the panel's animate prop stopped tracking it; a
        pointer-events toggle and an opacity transition have no such ambiguity
        and cost nothing.
      */}
      <button
        type="button"
        aria-label="Close menu"
        aria-hidden={!open || isLarge}
        tabIndex={open && !isLarge ? 0 : -1}
        onClick={close}
        className={cn(
          "fixed inset-0 top-(--topbar-height) z-30 bg-black/50 lg:hidden",
          "transition-opacity duration-200",
          open && !isLarge
            ? "opacity-100"
            : "pointer-events-none opacity-0",
        )}
      />

      <div
        className={cn(
          "pt-(--topbar-height) transition-[margin] duration-300",
          "[transition-timing-function:var(--ease-out-expo)]",
          // Below lg the sidebar floats over the content, so no margin at all.
          open ? "lg:ml-(--sidebar-width)" : "lg:ml-(--rail-width)",
        )}
      >
        <main
          id="main"
          className="mx-auto w-full max-w-[2200px] px-4 pb-16 md:px-6"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
