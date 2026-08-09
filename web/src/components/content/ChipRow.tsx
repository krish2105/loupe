import Link from "next/link";
import { MarkNode } from "@/components/mark/Mark";
import { cn } from "@/lib/utils";

/**
 * Feed filters.
 *
 * Two, and both are real. Topic chips need topics, which arrive with the
 * pipeline in Phase 5 — a row of decorative topic pills now would be a surface
 * that reads as finished and is not.
 *
 * "Searchable inside" is the honest one: it filters to the talks that carry a
 * transcript, which is the §4 split made usable rather than merely explained.
 */
export function ChipRow({ active }: { active: "all" | "searchable" }) {
  const chips = [
    { key: "all" as const, label: "All", href: "/" },
    { key: "searchable" as const, label: "Searchable inside", href: "/?only=searchable" },
  ];

  return (
    <nav
      aria-label="Filter the feed"
      className={cn(
        "no-scrollbar sticky top-(--topbar-height) z-20 -mx-4 flex gap-3",
        "overflow-x-auto bg-canvas px-4 py-3 md:-mx-6 md:px-6",
      )}
    >
      {chips.map((chip) => {
        const isActive = chip.key === active;
        return (
          <Link
            key={chip.key}
            href={chip.href}
            aria-current={isActive ? "true" : undefined}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-(--radius-sm)",
              "px-3 py-1.5 text-(length:--step--1) transition-colors",
              isActive
                ? "bg-ink text-canvas"
                : "bg-surface text-ink hover:bg-rule",
            )}
          >
            {chip.key === "searchable" && !isActive && <MarkNode />}
            {chip.label}
          </Link>
        );
      })}
    </nav>
  );
}
