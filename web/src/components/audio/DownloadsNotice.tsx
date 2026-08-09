"use client";

import { useEffect, useState } from "react";
import { storageEstimate } from "./download";

/**
 * What this device is actually holding.
 *
 * The list above is the server's record of what was asked for, on any device.
 * This is the browser's own accounting, and the two can legitimately differ —
 * downloading on a phone does not put bytes on a laptop. Showing both is more
 * honest than picking one and letting someone wonder why the number is wrong.
 */
export function DownloadsNotice() {
  const [room, setRoom] = useState<{ usage: number; quota: number } | null>(null);

  useEffect(() => {
    void storageEstimate().then(setRoom);
  }, []);

  if (!room) return null;

  return (
    <p className="mt-8 text-(length:--step--2) text-muted">
      This device is storing {megabytes(room.usage)} of Loupe data, out of about{" "}
      {megabytes(room.quota)} the browser will allow. Downloads live on the
      device that made them, so an episode saved here is not saved elsewhere.
    </p>
  );
}

function megabytes(bytes: number): string {
  const mb = bytes / 1_000_000;
  return mb >= 1000 ? `${(mb / 1000).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}
