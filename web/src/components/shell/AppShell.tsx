"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RailIcon, type RailIconName } from "./RailIcon";
import { SearchCapsule } from "./SearchCapsule";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Wordmark } from "./Wordmark";
import { cn } from "@/lib/utils";

/**
 * The app frame.
 *
 * A 56px icon rail and nothing else. There is no header band, because the
 * thumbnail grid is the design and the chrome recedes (§7.2) — and because
 * search belongs over the content, not above it.
 *
 * Below md the rail becomes bottom navigation and the capsule sits inline,
 * which is the arrangement §9 already specifies for the video page.
 */

type NavItem = { href: string; label: string; icon: RailIconName };

// Named by what the person controls, never by how the system is built (§7.6).
const NAV: NavItem[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/shorts", label: "Shorts", icon: "shorts" },
  { href: "/subscriptions", label: "Subscriptions", icon: "subscriptions" },
  { href: "/history", label: "History", icon: "history" },
  { href: "/saved", label: "Watch later", icon: "saved" },
  { href: "/playlists", label: "Playlists", icon: "playlists" },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      title={item.label}
      className={cn(
        "group relative grid size-11 place-items-center rounded-(--radius-sm)",
        "transition-colors",
        active ? "text-screen" : "text-dust hover:text-screen",
      )}
    >
      <RailIcon name={item.icon} />
      <span className="sr-only">{item.label}</span>

      {/* The active indicator is achromatic — the accent is reserved for the
          semantic layer, so navigation never borrows it. */}
      {active && (
        <span
          aria-hidden="true"
          className={cn(
            "absolute rounded-full bg-screen",
            "left-0 top-1/2 h-5 w-[2px] -translate-y-1/2",
            "max-md:left-1/2 max-md:top-auto max-md:bottom-0",
            "max-md:h-[2px] max-md:w-5 max-md:-translate-x-1/2 max-md:translate-y-0",
          )}
        />
      )}
    </Link>
  );
}

/** Only what the shell renders. Passing the whole Supabase user would leak
 *  tokens and metadata into the client bundle for no benefit. */
export type ShellUser = { email: string; initial: string };

function AccountControl({ user }: { user: ShellUser | null }) {
  if (!user) {
    return (
      <Link
        href="/login"
        title="Sign in"
        className="grid size-9 place-items-center rounded-(--radius-sm) text-dust transition-colors hover:text-screen"
      >
        <svg
          viewBox="0 0 20 20"
          aria-hidden="true"
          className="size-[18px]"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          <circle cx="10" cy="7" r="3.25" />
          <path d="M4 16.5a6 6 0 0 1 12 0" />
        </svg>
        <span className="sr-only">Sign in</span>
      </Link>
    );
  }

  return (
    <form action="/auth/signout" method="post">
      <button
        type="submit"
        title={`Sign out of ${user.email}`}
        className={cn(
          "grid size-9 place-items-center rounded-full",
          "border border-rule bg-riser font-mono text-(length:--step--1)",
          "text-dust transition-colors hover:text-screen",
        )}
      >
        {user.initial}
        <span className="sr-only">Sign out of {user.email}</span>
      </button>
    </form>
  );
}

export function AppShell({
  children,
  user = null,
}: {
  children: React.ReactNode;
  user?: ShellUser | null;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-dvh">
      {/* Rail — desktop */}
      <nav
        aria-label="Sections"
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden w-(--rail-width) md:flex",
          "flex-col items-center gap-1 border-r border-rule bg-hall py-3",
        )}
      >
        <Link
          href="/"
          className="mb-3 grid size-11 place-items-center rounded-(--radius-sm)"
        >
          <Wordmark variant="glyph" />
        </Link>

        {NAV.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} />
        ))}

        <div className="mt-auto flex flex-col items-center gap-2">
          <ThemeToggle />
          <AccountControl user={user} />
        </div>
      </nav>

      {/* Slim top row — mobile only. Carries the wordmark and the theme control
          that the rail holds on desktop. */}
      <div
        className={cn(
          "sticky top-0 z-20 flex items-center justify-between",
          "border-b border-rule bg-hall px-4 py-2.5 md:hidden",
        )}
      >
        <Link href="/">
          <Wordmark variant="full" className="text-(length:--step-1)!" />
        </Link>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <AccountControl user={user} />
        </div>
      </div>

      <div className="md:pl-(--rail-width)">
        {/* backdrop-filter is permitted on navigation chrome only (§7.3); it is
            never applied to the grid, where it costs 15–30% FPS. */}
        <div
          className={cn(
            "sticky top-0 z-10 flex justify-center",
            "bg-hall/85 px-4 py-3 backdrop-blur-md",
            "max-md:top-[52px]",
          )}
        >
          <SearchCapsule />
        </div>

        <main
          id="main"
          className="mx-auto w-full max-w-[1600px] px-4 pb-24 md:px-6 md:pb-12"
        >
          {children}
        </main>
      </div>

      {/* Bottom navigation — mobile */}
      <nav
        aria-label="Sections"
        className={cn(
          "fixed inset-x-0 bottom-0 z-30 flex items-center justify-around",
          "border-t border-rule bg-hall px-2 pb-[env(safe-area-inset-bottom)] pt-1 md:hidden",
        )}
      >
        {NAV.map((item) => (
          <NavLink key={item.href} item={item} active={isActive(pathname, item.href)} />
        ))}
      </nav>
    </div>
  );
}
