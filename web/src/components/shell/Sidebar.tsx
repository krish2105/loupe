"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Avatar } from "./Avatar";
import { Icon, type IconName } from "./Icon";
import { cn } from "@/lib/utils";

/**
 * The sidebar.
 *
 * Two forms, as the mainstream convention has them: an expanded 240px panel
 * with labelled sections, and a 72px rail of icons with labels beneath. The
 * rail is what shows when the panel is collapsed on desktop.
 *
 * The subscription list is the reason this exists rather than the old icon
 * rail — a video product's sidebar is mostly other people's channels, and
 * their avatars are what make it navigable at a glance.
 */

export type SidebarChannel = {
  id: string;
  handle: string;
  name: string;
  avatar_url: string | null;
};

type Item = { href: string; label: string; icon: IconName };

const PRIMARY: Item[] = [
  { href: "/", label: "Home", icon: "home" },
  // Back, now that the route exists. It was removed in Phase 3 because it had
  // pointed at a 404 since Phase 0 — a nav item is a promise.
  { href: "/shorts", label: "Shorts", icon: "shorts" },
  { href: "/listen", label: "Listen", icon: "audio" },
  { href: "/subscriptions", label: "Subscriptions", icon: "subscriptions" },
];

// "You" — everything that belongs to the person rather than the catalogue.
const YOURS: Item[] = [
  { href: "/history", label: "History", icon: "history" },
  { href: "/playlists", label: "Playlists", icon: "playlists" },
  { href: "/saved", label: "Watch later", icon: "watchLater" },
  { href: "/saved?list=liked", label: "Liked videos", icon: "liked" },
];

function isActive(pathname: string, href: string) {
  const path = href.split("?")[0];
  return path === "/" ? pathname === "/" : pathname.startsWith(path);
}

function SidebarLink({
  item,
  active,
  compact,
}: {
  item: Item;
  active: boolean;
  compact?: boolean;
}) {
  if (compact) {
    return (
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex w-full flex-col items-center gap-1 rounded-(--radius-md) px-1 py-4",
          "transition-colors hover:bg-surface",
          active ? "text-ink" : "text-ink/90",
        )}
      >
        <Icon name={item.icon} filled={active} className="size-6" />
        <span className="text-[10px] leading-tight">{item.label.split(" ")[0]}</span>
      </Link>
    );
  }

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-6 rounded-(--radius-md) px-3 py-2.5",
        "text-(length:--step--1) transition-colors",
        active ? "bg-surface font-medium text-ink" : "text-ink hover:bg-surface",
      )}
    >
      <Icon name={item.icon} filled={active} />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

function Section({
  title,
  children,
}: {
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-rule px-3 py-3">
      {title && (
        <h2 className="px-3 pb-1 pt-2 text-(length:--step-0) font-medium">
          {title}
        </h2>
      )}
      {children}
    </div>
  );
}

export function Sidebar({
  open,
  channels,
  isSignedIn,
}: {
  open: boolean;
  channels: SidebarChannel[];
  isSignedIn: boolean;
}) {
  const pathname = usePathname();

  return (
    <>
      {/*
        The slide is a CSS transform, not a Motion animation.

        The Motion version wrote translateX(-100%) on mount and then never
        updated it when `open` changed — the scrim reacted, the panel did not.
        A transform class with a transition is deterministic, composited on the
        GPU, and already covered by the global prefers-reduced-motion guard in
        globals.css, so Motion was buying nothing here.
      */}
      <nav
        aria-label="Sections"
        className={cn(
          "fixed bottom-0 left-0 top-(--topbar-height) z-40 w-(--sidebar-width)",
          "overflow-y-auto overscroll-contain bg-canvas",
          "transition-transform duration-300",
          "[transition-timing-function:var(--ease-out-expo)]",
          open ? "translate-x-0" : "-translate-x-full",
          // A drawer above the content on small screens, part of the layout on
          // large ones.
          "max-lg:border-r max-lg:border-rule max-lg:shadow-2xl",
        )}
      >
        <Section>
          {PRIMARY.map((item) => (
            <SidebarLink
              key={item.href}
              item={item}
              active={isActive(pathname, item.href)}
            />
          ))}
        </Section>

        <Section title="You">
          {YOURS.map((item) => (
            <SidebarLink
              key={item.href}
              item={item}
              active={isActive(pathname, item.href)}
            />
          ))}
        </Section>

        <Section title="Subscriptions">
          {!isSignedIn ? (
            <p className="px-3 py-2 text-pretty text-(length:--step--1) text-muted">
              Sign in to follow channels and see their new talks here.
            </p>
          ) : channels.length === 0 ? (
            <p className="px-3 py-2 text-pretty text-(length:--step--1) text-muted">
              Channels you follow appear here.
            </p>
          ) : (
            channels.map((channel) => (
              <Link
                key={channel.id}
                href={`/c/${channel.handle}`}
                className={cn(
                  "flex items-center gap-4 rounded-(--radius-md) px-3 py-2",
                  "text-(length:--step--1) transition-colors hover:bg-surface",
                )}
              >
                <Avatar name={channel.name} size={24} />
                <span className="truncate">{channel.name}</span>
              </Link>
            ))
          )}
        </Section>

        <p className="px-6 py-6 text-pretty text-(length:--step--2) text-muted">
          Loupe — search inside talks, not just their titles.
        </p>
      </nav>

      {/* Icon rail — desktop only, and only while the panel is closed. */}
      <nav
        aria-label="Sections"
        className={cn(
          "fixed bottom-0 left-0 top-(--topbar-height) z-30 w-(--rail-width)",
          "flex-col items-center gap-1 overflow-y-auto bg-canvas px-1 py-1",
          open ? "hidden" : "hidden lg:flex",
        )}
      >
        {[...PRIMARY, ...YOURS.slice(0, 2)].map((item) => (
          <SidebarLink
            key={item.href}
            item={item}
            active={isActive(pathname, item.href)}
            compact
          />
        ))}
      </nav>
    </>
  );
}
