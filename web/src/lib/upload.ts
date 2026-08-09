/**
 * Upload tickets, as data.
 *
 * The page that uses this is unavoidably imperative — it holds an
 * XMLHttpRequest, because `fetch` still cannot report upload progress in any
 * browser, and a video upload with no progress bar is indistinguishable from a
 * hang. Everything around that request is decided here instead, where it can be
 * tested without a network, a file, or a provider.
 *
 * The ticket shape is the media service's, which serves two providers with
 * genuinely different needs: S3 signs the URL itself and wants a plain PUT,
 * Bunny wants a POST carrying a separate signature. Rather than a lowest common
 * denominator that fits neither, unused fields are absent and `method` says
 * which shape arrived.
 */

export type UploadTicket = {
  upload_url: string;
  /** Unix seconds. */
  expires_at: number;
  method: string;
  library_id?: string | null;
  video_guid?: string | null;
  signature?: string | null;
};

/**
 * Why this ticket cannot be used, or null if it can.
 *
 * A ticket that expired between being issued and being used fails as a 403
 * from the bucket with an XML body, which surfaces to someone uploading a
 * conference talk as "Upload failed" and nothing else. Catching it here costs
 * one comparison and produces a sentence that says what to do.
 */
export function ticketProblem(
  ticket: UploadTicket,
  now: number = Date.now(),
): string | null {
  if (!ticket.upload_url) {
    return "The media service issued a ticket with no upload address.";
  }

  if (ticket.expires_at * 1000 <= now) {
    return "That upload ticket expired before the file could be sent. Try again.";
  }

  if (ticket.method === "POST" && !ticket.signature) {
    // The Bunny shape without the one field that makes it usable.
    return "The media service issued an incomplete ticket for this provider.";
  }

  return null;
}

/**
 * Whether the file itself is worth sending.
 *
 * Checked before the ticket is requested, so a mistake costs nothing and the
 * message arrives immediately rather than after a long upload.
 */
export function fileProblem(file: File | null, maxBytes: number): string | null {
  if (!file) return "Choose a video file first.";
  if (file.size === 0) return "That file is empty.";
  if (file.size > maxBytes) {
    return `That file is ${formatBytes(file.size)}. The limit is ${formatBytes(maxBytes)}.`;
  }
  if (!file.type.startsWith("video/") && !file.type.startsWith("audio/")) {
    return "That does not look like a video or audio file.";
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  // One decimal below 10, none above — "1.4 GB" reads better than "1 GB", and
  // "847 MB" better than "847.3 MB".
  return `${value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

/**
 * What the progress line says.
 *
 * `total` can be 0 when the browser cannot determine length, which is rare but
 * real — reporting "NaN%" at that moment is worse than saying nothing precise.
 */
export function progressLabel(loaded: number, total: number): string {
  if (total <= 0) return `Sending… ${formatBytes(loaded)}`;
  const percent = Math.min(100, Math.round((loaded / total) * 100));
  return `Sending… ${percent}% of ${formatBytes(total)}`;
}
