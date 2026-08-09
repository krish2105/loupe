"use client";

import { useRef, useState } from "react";
import { Icon } from "@/components/shell/Icon";
import { cn } from "@/lib/utils";
import {
  fileProblem,
  formatBytes,
  progressLabel,
  ticketProblem,
  type UploadTicket,
} from "@/lib/upload";

const MEDIA_URL = process.env.NEXT_PUBLIC_MEDIA_URL ?? "";

/**
 * Two gigabytes. Not a provider limit — a limit on how long someone can be
 * asked to wait before finding out it failed. The transcoder is a single
 * always-free ARM box with two cores; a file larger than this would sit in the
 * queue for hours whatever happened at this end.
 */
const MAX_BYTES = 2 * 1024 * 1024 * 1024;

/**
 * Upload a talk.
 *
 * Ask the media service for a signed ticket, then send the file straight to the
 * bucket. The bytes never pass through our infrastructure — §5 keeps provider
 * credentials in the media service, and proxying video through a free-tier
 * instance would make uploads the single most expensive thing the platform
 * does, on the tier least able to afford it.
 *
 * XMLHttpRequest rather than fetch, for the one reason that still justifies it:
 * fetch cannot report upload progress in any browser. A video upload without a
 * progress bar is indistinguishable from a hang, and someone watching a still
 * screen for four minutes reloads the page and starts again.
 *
 * Everything decidable is decided in lib/upload.ts, where it is tested without
 * a network. What is left here is genuinely imperative.
 */
export default function UploadPage() {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [pending, setPending] = useState(false);

  // Held so the cancel button can reach it. A ref rather than state: nothing
  // renders from it, and a re-render per upload would be for nothing.
  const request = useRef<XMLHttpRequest | null>(null);

  function reset() {
    setPending(false);
    setProgress(null);
    request.current = null;
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setStatus(null);
    setProgress(null);

    if (!MEDIA_URL) {
      setError(
        "The media service is not connected in this environment. Set NEXT_PUBLIC_MEDIA_URL and start services/media.",
      );
      return;
    }

    // Checked before the ticket is requested, so a mistake costs nothing.
    const problem = fileProblem(file, MAX_BYTES);
    if (problem) {
      setError(problem);
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

    if (!ticketResponse) {
      reset();
      setStatus(null);
      /**
       * A rejected fetch is not proof the service is down. A response the
       * browser refuses to hand over — a server error carrying no CORS headers,
       * most often — rejects here in exactly the same way, and this message
       * used to send people to check on a service that was running and
       * answering. It says both possibilities now, in the order worth checking.
       */
      setError(
        `No usable answer from the media service at ${MEDIA_URL}. It may be ` +
          `down, or it may have answered with an error the browser blocked. ` +
          `The console will say which.`,
      );
      return;
    }

    if (!ticketResponse.ok) {
      reset();
      setStatus(null);
      const body = await ticketResponse.json().catch(() => null);
      setError(body?.detail ?? `The media service answered ${ticketResponse.status}.`);
      return;
    }

    const ticket = (await ticketResponse.json()) as UploadTicket;

    const ticketIssue = ticketProblem(ticket);
    if (ticketIssue) {
      reset();
      setStatus(null);
      setError(ticketIssue);
      return;
    }

    setStatus(`Sending ${formatBytes(file!.size)} to the provider…`);
    send(ticket, file!);
  }

  function send(ticket: UploadTicket, chosen: File) {
    const xhr = new XMLHttpRequest();
    request.current = xhr;

    xhr.open(ticket.method || "PUT", ticket.upload_url, true);

    // The presigned URL signs only the host, so this header is not part of the
    // signature and cannot invalidate it. It is sent because the bucket stores
    // it, and the transcoder reads it to decide how to treat the file.
    if (chosen.type) xhr.setRequestHeader("Content-Type", chosen.type);
    if (ticket.signature) {
      xhr.setRequestHeader("AuthorizationSignature", ticket.signature);
    }

    xhr.upload.addEventListener("progress", (event) => {
      setProgress(event.lengthComputable ? event.loaded / event.total : null);
      setStatus(progressLabel(event.loaded, event.lengthComputable ? event.total : 0));
    });

    xhr.addEventListener("load", () => {
      reset();
      if (xhr.status >= 200 && xhr.status < 300) {
        setStatus(
          "Uploaded. Loupe is transcoding it now — it becomes watchable first, then searchable once the transcript is indexed.",
        );
        setFile(null);
        setTitle("");
        return;
      }
      setStatus(null);
      // The bucket answers failures with XML, which is not worth showing.
      // The status code is the part that helps.
      setError(
        xhr.status === 403
          ? "The provider refused the upload — the ticket may have expired. Try again."
          : `The provider answered ${xhr.status}.`,
      );
    });

    xhr.addEventListener("error", () => {
      reset();
      setStatus(null);
      setError("The connection dropped during the upload. Nothing was saved.");
    });

    xhr.addEventListener("abort", () => {
      reset();
      setStatus(null);
      setError("Upload cancelled.");
    });

    xhr.send(chosen);
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
            disabled={pending}
            placeholder="What is the talk called?"
            className={cn(
              "mt-2 h-11 w-full rounded-(--radius-sm) border border-rule bg-canvas px-3",
              "text-(length:--step-0) outline-none transition-colors",
              "placeholder:text-muted focus:border-brand disabled:opacity-60",
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
              pending && "pointer-events-none opacity-60",
            )}
          >
            <Icon name="create" className="size-8 text-muted" />
            <span className="text-(length:--step--1)">
              {file ? `${file.name} · ${formatBytes(file.size)}` : "Choose a file"}
            </span>
            <span className="text-(length:--step--2) text-muted">
              MP4 or MOV, up to {formatBytes(MAX_BYTES)}. Sent directly to the
              provider, not through Loupe.
            </span>
          </label>
          <input
            id="file"
            type="file"
            accept="video/*,audio/*"
            disabled={pending}
            className="sr-only"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>

        {/* Reserved height, so the form does not jump when a message appears. */}
        {progress !== null && (
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            aria-label="Upload progress"
            className="h-1 w-full overflow-hidden rounded-(--radius-pill) bg-surface"
          >
            <div
              className="h-full bg-brand transition-[width] duration-200"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
        )}

        {status && (
          <p role="status" className="text-pretty text-(length:--step--1) text-muted">
            {status}
          </p>
        )}
        {error && (
          <p role="alert" className="text-pretty text-(length:--step--1) text-danger">
            {error}
          </p>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={pending}
            className={cn(
              "h-11 flex-1 rounded-(--radius-pill) bg-brand",
              "text-(length:--step-0) font-medium text-white",
              "transition-opacity hover:opacity-90 disabled:opacity-50",
            )}
          >
            {pending ? "Uploading…" : "Upload"}
          </button>

          {pending && (
            <button
              type="button"
              onClick={() => request.current?.abort()}
              className={cn(
                "h-11 rounded-(--radius-pill) border border-rule px-5",
                "text-(length:--step-0) transition-colors hover:border-brand",
              )}
            >
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
