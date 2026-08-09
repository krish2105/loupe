"use client";

import { useEffect } from "react";

/**
 * Registers the service worker (ADR 0003).
 *
 * Registration is deliberately not conditional on the environment. A service
 * worker that only exists in production is one that is never exercised until
 * it breaks in production, and the failure mode — a stale shell served to
 * everyone — is the kind that outlives the deploy that caused it.
 */
export function ServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Registration fails on insecure origins and in some private modes.
      // Offline support is an enhancement; losing it costs nothing else.
    });
  }, []);

  return null;
}
