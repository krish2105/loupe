"use client";

import { useEffect, useRef, useState } from "react";
import { AUTO, qualityLabel, type QualityOption } from "./quality-options";
import { cn } from "@/lib/utils";

/**
 * The quality control.
 *
 * Hand-built rather than generated. §8.1 rule 2 keeps the player out of the
 * component catalogue, and a menu that lives inside player chrome is player
 * chrome: it sits over video, it closes on the same Escape that leaves full
 * screen, and it must not steal the keyboard bindings in §9.1.
 *
 * Renders nothing when there is nothing to choose. A single-rendition stream
 * and native HLS both arrive here with an empty list, and a disabled control
 * explaining an absence is noisier than no control.
 */
export function QualityMenu({
  options,
  selected,
  activeHeight,
  onSelect,
}: {
  options: QualityOption[];
  selected: number;
  activeHeight: number | null;
  onSelect: (index: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      // Escape closes the menu and nothing else. Without stopping it here the
      // same key would also leave full screen, so one press would undo two
      // things a viewer only meant to undo one of.
      event.stopPropagation();
      setOpen(false);
    };

    const onPointerDown = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };

    // Capture, so both handlers run before the document-level player bindings.
    document.addEventListener("keydown", onKeyDown, true);
    document.addEventListener("pointerdown", onPointerDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.removeEventListener("pointerdown", onPointerDown, true);
    };
  }, [open]);

  if (options.length === 0) return null;

  const label = qualityLabel(selected, activeHeight);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        aria-haspopup="menu"
        aria-expanded={open}
        // The visible text is a resolution; the accessible name says what
        // pressing it does, because "Auto 1080p" alone does not.
        aria-label={`Quality, currently ${label}`}
        className={cn(
          "rounded-(--radius-sm) px-2 py-1",
          "font-mono text-(length:--step--2) text-ink/70 tabular-nums",
          "transition-colors hover:text-ink",
          open && "text-ink",
        )}
      >
        {label}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Quality"
          className={cn(
            "absolute bottom-full right-0 mb-2 min-w-28 overflow-hidden",
            "rounded-(--radius-sm) border border-rule bg-surface py-1 shadow-lg",
          )}
        >
          {options.map((option) => {
            const isSelected = option.index === selected;
            return (
              <button
                key={option.index}
                type="button"
                role="menuitemradio"
                aria-checked={isSelected}
                onClick={() => {
                  onSelect(option.index);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-1.5 text-left",
                  "font-mono text-(length:--step--2) tabular-nums",
                  "transition-colors hover:bg-canvas",
                  isSelected ? "text-ink" : "text-muted",
                )}
              >
                <span aria-hidden="true" className="w-2">
                  {isSelected ? "•" : ""}
                </span>
                {option.label}
                {option.index === AUTO && activeHeight && (
                  <span className="ml-auto text-muted">{activeHeight}p</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
