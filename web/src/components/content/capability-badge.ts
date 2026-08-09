import type { Capabilities } from "@/lib/catalogue";

/**
 * What a card says a talk can do.
 *
 * Pure, because the bug this exists to prevent was a wrong branch rather than a
 * wrong pixel: a card that read `processing` alone promised "watchable now" on
 * talks the watch page then refused to play. That is a data question, and it is
 * cheaper to answer in a test than by clicking through a feed looking for the
 * three rows in twenty-one that are at the wrong stage.
 */
export type BadgeKind = "searchable" | "indexing" | "processing" | "none";

/**
 * `processing` is true for every stage before a talk is searchable, and those
 * stages are not alike. From `transcoded` onward there is a stream to watch
 * while indexing finishes. At `uploaded` and `transcoding` there is no media at
 * all. Only `playable` tells the two apart, so both flags are read here.
 *
 * Order matters. Searchable wins, because it is the strongest thing a card can
 * say and it implies the rest.
 */
export function badgeFor(capabilities: Capabilities): BadgeKind {
  if (capabilities.askable) return "searchable";
  if (!capabilities.processing) return "none";
  return capabilities.playable ? "indexing" : "processing";
}
