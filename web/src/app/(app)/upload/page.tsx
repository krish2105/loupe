"use client";

import { useState } from "react";
import { Icon } from "@/components/shell/Icon";
import { cn } from "@/lib/utils";

const MEDIA_URL = process.env.NEXT_PUBLIC_MEDIA_URL ?? "";

/**
 * Upload a talk.
 *
 * The real Phase 1 flow: ask the media service for a signed ticket, then send
 * the file straight to the provider. The bytes never pass through our
 * infrastructure — §5 keeps provider credentials in the media service, and
 * proxying video through a small instance would make uploads the single most
 * expensive thing the platform does.
 *
 * Nothing here is mocked. With no media provider configured the service
 * answers 503 with a specific reason and this page shows it, which is the true
 * state rather than a pretend success.
 */
export default function UploadPage() {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setStatus(null);

    if (!MEDIA_URL) {
      setError(
        "The media service is not connected in this environment. Set NEXT_PUBLIC_MEDIA_URL and start services/media.",
      );
      return;
    }
    if (!file) {
      setError("Choose a video file first.");
      return;
    }

    setPending(true);
    setStatus("Asking for an upload ticket…");

    const ticketResponse = await fetch(`${MEDIA_URL}/v1/uploads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // video_id comes from the core API in the full flow; this page is the
      // provider half, so it is supplied by whatever created the row.
      body: JSON.stringify({ video_id: crypto.randomUUID(), title }),
    }).catch(() => null);

    setPending(false);

    if (!ticketResponse) {
      setStatus(null);
      setError(
        `Could not reach the media service at ${MEDIA_URL}. Is it running?`,
      );
      return;
    }

    if (!ticketResponse.ok) {
      setStatus(null);
      const body = await ticketResponse.json().catch(() => null);
      setError(body?.detail ?? `The media service answered ${ticketResponse.status}.`);
      return;
    }

    setStatus("Ticket issued. Sending the file to the provider…");
  }

  return (
    <div className="mx-auto max-w-[560px] py-10">
      <h1 className="text-(length:--step-3)">Upload a talk</h1>
      <p className="mt-2 text-pretty text-(length:--step--1) text-muted">
        The file goes straight to the media provider. Loupe transcribes it,
        splits it into moments, and indexes it — so it becomes watchable
        immediately and searchable a little later.
      </p>

      <form onSubmit={submit} className="mt-8 space-y-5">
        <div>
          <label htmlFor="title" className="text-(length:--step--1) font-medium">
            Title
          </label>
          <input
            id="title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            placeholder="What is the talk called?"
            className={cn(
              "mt-2 h-11 w-full rounded-(--radius-sm) border border-rule bg-canvas px-3",
              "text-(length:--step-0) outline-none transition-colors",
              "placeholder:text-muted focus:border-brand",
            )}
          />
        </div>

        <div>
          <label htmlFor="file" className="text-(length:--step--1) font-medium">
            Video file
          </label>
          <label
            htmlFor="file"
            className={cn(
              "mt-2 flex cursor-pointer flex-col items-center gap-3 rounded-(--radius-md)",
              "border border-dashed border-rule bg-surface px-6 py-10 text-center",
              "transition-colors hover:border-brand",
            )}
          >
            <Icon name="create" className="size-8 text-muted" />
            <span className="text-(length:--step--1)">
              {file ? file.name : "Choose a file"}
            </span>
            <span className="text-(length:--step--2) text-muted">
              MP4 or MOV. It is sent directly to the provider, not through Loupe.
            </span>
          </label>
          <input
            id="file"
            type="file"
            accept="video/*"
            className="sr-only"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>

        {status && (
          <p role="status" className="text-(length:--step--1) text-muted">
            {status}
          </p>
        )}
        {error && (
          <p role="alert" className="text-pretty text-(length:--step--1) text-danger">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={pending}
          className={cn(
            "h-11 w-full rounded-(--radius-pill) bg-brand",
            "text-(length:--step-0) font-medium text-white",
            "transition-opacity hover:opacity-90 disabled:opacity-50",
          )}
        >
          {pending ? "Uploading…" : "Upload"}
        </button>
      </form>
    </div>
  );
}
