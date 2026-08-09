import type { Metadata } from "next";

export const metadata: Metadata = { title: "Offline" };

/**
 * What the service worker serves when there is no connection.
 *
 * Written to the §7.6 standard for failure states: say what happened and what
 * can still be done, in the interface's voice. It does not apologise and it
 * does not promise that anything is being retried.
 */
export default function OfflinePage() {
  return (
    <div className="mx-auto grid min-h-dvh max-w-[46ch] place-content-center px-6 text-center">
      <h1 className="text-(length:--step-3)">No connection</h1>
      <p className="mt-3 text-pretty text-(length:--step--1) text-muted">
        Loupe needs the network to load talks and episodes. Pages you have
        already opened are still here.
      </p>
      <p className="mt-6 text-pretty text-(length:--step--2) text-muted">
        Downloading episodes to listen offline is not built yet. The catalogue
        points at streams Loupe does not own, and caching those is a licensing
        question rather than a missing feature.
      </p>
    </div>
  );
}
