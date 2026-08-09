"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { motion, useReducedMotion } from "motion/react";
import { Avatar } from "./Avatar";
import { Icon } from "./Icon";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Wordmark } from "./Wordmark";
import { cn } from "@/lib/utils";

/**
 * The top bar.
 *
 * The old design put search in a floating capsule over the content and had no
 * header at all. This is the mainstream arrangement instead, per ADR 0002:
 * menu and wordmark left, search centred, actions right.
 */

const noSubscription = () => () => {};

function IconButton({
  label,
  onClick,
  href,
  children,
  badge,
}: {
  label: string;
  onClick?: () => void;
  href?: string;
  children: React.ReactNode;
  badge?: number;
}) {
  const className = cn(
    "relative grid size-10 place-items-center rounded-full",
    "text-ink transition-colors hover:bg-surface",
  );

  const content = (
    <>
      {children}
      {badge ? (
        <span
          className={cn(
            "absolute right-1 top-1 grid min-w-4 place-items-center rounded-full",
            "bg-brand px-1 text-[10px] font-medium leading-4 text-white",
          )}
        >
          {badge > 9 ? "9+" : badge}
        </span>
      ) : null}
      <span className="sr-only">{label}</span>
    </>
  );

  if (href) {
    return (
      <Link href={href} title={label} className={className}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} title={label} className={className}>
      {content}
    </button>
  );
}

function Search() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const reduce = useReducedMotion();

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
      onSubmit={(event) => {
        event.preventDefault();
        if (query.trim()) router.push(`/search?q=${encodeURIComponent(query.trim())}`);
      }}
      className="flex min-w-0 flex-1 items-center justify-center gap-2"
    >
      <div className="flex min-w-0 max-w-[560px] flex-1 items-center">
        <motion.div
          animate={{ scale: focused && !reduce ? 1.01 : 1 }}
          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
          className={cn(
            "flex min-w-0 flex-1 items-center gap-2 rounded-l-(--radius-pill)",
            "border border-rule bg-canvas py-2 pl-4 pr-3 transition-colors",
            focused && "border-brand",
          )}
        >
          {focused && <Icon name="search" className="size-4 shrink-0 text-muted" />}
          <label htmlFor="site-search" className="sr-only">
            Search talks and moments
          </label>
          <input
            id="site-search"
            ref={inputRef}
            type="search"
            autoComplete="off"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder="Search a talk, or a moment inside one"
            className={cn(
              "min-w-0 flex-1 bg-transparent text-(length:--step--1)",
              "text-ink outline-none placeholder:text-muted",
            )}
          />
          <kbd
            className={cn(
              "hidden shrink-0 rounded-(--radius-sm) border border-rule",
              "px-1.5 py-0.5 font-mono text-[10px] text-muted md:block",
            )}
          >
            {isMac ? "⌘K" : "Ctrl K"}
          </kbd>
        </motion.div>

        <button
          type="submit"
          title="Search"
          className={cn(
            "grid h-[38px] w-16 shrink-0 place-items-center",
            "rounded-r-(--radius-pill) border border-l-0 border-rule bg-surface",
            "text-ink transition-colors hover:bg-brand hover:text-white",
          )}
        >
          <Icon name="search" className="size-5" />
          <span className="sr-only">Search</span>
        </button>
      </div>

      <IconButton label="Search by voice">
        <Icon name="mic" className="size-5" />
      </IconButton>
    </form>
  );
}

export function TopBar({
  onToggleSidebar,
  user,
  unread = 0,
}: {
  onToggleSidebar: () => void;
  user: { email: string; initial: string } | null;
  unread?: number;
}) {
  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 flex h-(--topbar-height) items-center gap-2",
        "border-b border-rule bg-canvas px-2 md:px-4",
      )}
    >
      <div className="flex shrink-0 items-center gap-1">
        <IconButton label="Open menu" onClick={onToggleSidebar}>
          <Icon name="menu" className="size-6" />
        </IconButton>

        <Link href="/" className="flex items-center gap-1.5 rounded-(--radius-sm) px-1">
          <Wordmark variant="glyph" />
          <Wordmark variant="full" className="max-sm:hidden text-(length:--step-1)!" />
        </Link>
      </div>

      <Search />

      <div className="flex shrink-0 items-center gap-1">
        <Link
          href="/upload"
          className={cn(
            "hidden items-center gap-2 rounded-(--radius-pill) bg-surface px-4 py-2",
            "text-(length:--step--1) font-medium text-ink transition-colors",
            "hover:bg-brand hover:text-white sm:flex",
          )}
        >
          <Icon name="create" className="size-5" />
          Create
        </Link>

        <IconButton
          label={unread ? `Notifications, ${unread} unread` : "Notifications"}
          href="/notifications"
          badge={unread}
        >
          <Icon name="bell" className="size-6" />
        </IconButton>

        <ThemeToggle />

        {user ? (
          <Link href="/history" title={user.email} className="ml-1 grid size-9 place-items-center">
            <Avatar name={user.initial} size={32} />
            <span className="sr-only">Your account</span>
          </Link>
        ) : (
          <Link
            href="/login"
            className={cn(
              "ml-1 flex items-center gap-2 rounded-(--radius-pill) border border-rule",
              "px-3 py-1.5 text-(length:--step--1) font-medium text-brand",
              "transition-colors hover:bg-brand-faint",
            )}
          >
            <Icon name="user" className="size-5" />
            <span className="max-sm:hidden">Sign in</span>
          </Link>
        )}
      </div>
    </header>
  );
}
