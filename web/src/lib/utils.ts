import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

/**
 * Format seconds as a timecode.
 *
 * Citations, chapters, and the scrubber all render timestamps, and they must
 * agree exactly — §11.1 makes the whole intelligence layer depend on a
 * timestamp landing on the right moment, so there is one formatter, not three.
 * Hours are shown only when the talk is long enough to have them.
 */
export function formatTimecode(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  const pad = (n: number) => n.toString().padStart(2, "0");

  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(seconds)}`
    : `${minutes}:${pad(seconds)}`;
}
