"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";

/**
 * Clears the unread badge when the notifications page is opened.
 *
 * Reading the page *is* the read receipt, so this fires on mount rather than
 * behind a "mark all read" button — a button would ask someone to confirm
 * something they have already done.
 *
 * The rows arrive already rendered with their unread highlight, and the refresh
 * afterwards only updates the badge in the top bar. That ordering is
 * deliberate: clearing the highlight in the same paint would make the thing
 * you came to look at disappear as you looked at it.
 */
export function MarkRead({ unread }: { unread: number }) {
  const router = useRouter();

  useEffect(() => {
    if (!unread || !API_URL) return;

    let cancelled = false;

    (async () => {
      const supabase = createClient();
      if (!supabase) return;

      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) return;

      const response = await fetch(`${API_URL}/v1/me/notifications/read`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      // Refresh only on success. Refreshing after a failed write would re-render
      // the same unread state and schedule this effect again on every pass.
      if (response.ok && !cancelled) router.refresh();
    })();

    return () => {
      cancelled = true;
    };
  }, [unread, router]);

  return null;
}
