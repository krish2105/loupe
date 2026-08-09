/**
 * The quality menu, as data.
 *
 * A manifest is not a menu. It carries one entry per encoded variant, which
 * means several entries at the same height when a ladder has more than one
 * bitrate per resolution, in whatever order the packager emitted them. Offering
 * that list raw gives people two identical-looking "720p" rows and no way to
 * tell them apart.
 *
 * So the shape of the menu is decided here, in a pure function, away from both
 * hls.js and the DOM. §9.1 wanted adaptive bitrate never overridden; that was
 * right about the default and wrong about the ceiling — a viewer on a metered
 * connection has a reason to pin 360p that the algorithm cannot know. Auto
 * stays the default and stays first.
 */

/** One variant from the manifest. `index` is hls.js's own level index. */
export type QualityLevel = {
  index: number;
  height: number;
  bitrate: number;
};

/** `index` of -1 means automatic, which is hls.js's own convention. */
export type QualityOption = {
  index: number;
  label: string;
};

export const AUTO = -1;

/**
 * Menu rows: Auto, then each distinct height, highest first.
 *
 * Duplicate heights collapse to their highest bitrate, because that is the one
 * a person choosing "720p" means. Heights of zero — audio-only renditions,
 * which a manifest may legitimately carry — are dropped rather than shown as
 * "0p".
 */
export function qualityOptions(levels: QualityLevel[]): QualityOption[] {
  const best = new Map<number, QualityLevel>();

  for (const level of levels) {
    if (level.height <= 0) continue;
    const existing = best.get(level.height);
    if (!existing || level.bitrate > existing.bitrate) {
      best.set(level.height, level);
    }
  }

  // A single-rendition stream has no choice to offer, and a menu with one real
  // row is a control that does nothing.
  if (best.size < 2) return [];

  const rows = [...best.values()]
    .sort((a, b) => b.height - a.height)
    .map((level) => ({ index: level.index, label: `${level.height}p` }));

  return [{ index: AUTO, label: "Auto" }, ...rows];
}

/**
 * What the button reads.
 *
 * On Auto the resolution still matters to anyone wondering why a stream looks
 * soft, so it is shown alongside rather than hidden behind the word. That is
 * also what every player people already use does, and a quality control is not
 * the place to be original.
 */
export function qualityLabel(
  selected: number,
  activeHeight: number | null,
): string {
  if (selected !== AUTO) {
    return activeHeight ? `${activeHeight}p` : "Auto";
  }
  return activeHeight ? `Auto ${activeHeight}p` : "Auto";
}
