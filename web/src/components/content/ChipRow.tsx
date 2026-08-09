import Link from "next/link";
import { MarkNode } from "@/components/mark/Mark";
import { cn } from "@/lib/utils";

/**
 * Feed filters.
 *
 * Deliberately only two, and both are real. Topic chips need topics, which
 * arrive with the pipeline in Phase 5 — inventing a row of decorative topic
 * pills now would be the kind of fake surface that reads as finished and is
 * not.
 *
 * "Searchable" is the honest one: it filters to the talks that carry a
 * transcript, which is the §4 split made usable rather than merely explained.
 */
export function ChipRow({ active }: { active: "all" | "searchable" }) {
  const chips = [
    { key: "all" as const, label: "All talks", href: "/" },
    { key: "searchable" as const, label: "Searchable", href: "/?only=searchable" },
  ];

  return (
    <nav aria-label="Filter the feed" className="flex flex-wrap gap-2">
      {chips.map((chip) => {
        const isActive = chip.key === active;
        return (
          <Link
            key={chip.key}
            href={chip.href}
            aria-current={isActive ? "true" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-(--radius-pill)",
              "border px-3.5 py-1.5 text-(length:--step--1) transition-colors",
              isActive
                ? "border-screen bg-screen text-hall"
                : "border-rule bg-riser text-dust hover:text-screen",
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
