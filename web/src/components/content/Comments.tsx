"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Comment } from "@/lib/catalogue";
import { API_URL } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { cn, formatAge } from "@/lib/utils";

/**
 * Comments. One reply level (§6.2).
 *
 * The depth limit is enforced by a database trigger and surfaced by the API as
 * a 422; this component simply never offers a reply control on a reply, so the
 * limit is a shape rather than a rule people discover by hitting it.
 */

function Avatar({ name }: { name: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-full",
        "border border-rule bg-surface font-mono text-(length:--step--2) text-muted",
      )}
    >
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

function CommentBody({
  comment,
  onReply,
}: {
  comment: Comment;
  onReply?: () => void;
}) {
  return (
    <div className="flex gap-3">
      <Avatar name={comment.author.display_name} />
      <div className="min-w-0 flex-1">
        <p className="text-(length:--step--1)">
          <span className="font-medium">{comment.author.display_name}</span>{" "}
          <span className="text-muted">{formatAge(comment.created_at)}</span>
        </p>
        <p className="mt-1 whitespace-pre-line text-pretty text-(length:--step-0)">
          {comment.body}
        </p>
        {onReply && (
          <button
            type="button"
            onClick={onReply}
            className="mt-1.5 text-(length:--step--2) font-medium text-muted hover:text-ink"
          >
            Reply
          </button>
        )}
      </div>
    </div>
  );
}

function Composer({
  videoId,
  parentId,
  placeholder,
  onDone,
}: {
  videoId: string;
  parentId?: string;
  placeholder: string;
  onDone?: () => void;
}) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const supabase = createClient();
    if (!supabase || !API_URL) {
      setError("Commenting is not connected in this environment yet.");
      return;
    }

    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (!token) {
      setError("Sign in to post a comment.");
      return;
    }

    setPending(true);
    const response = await fetch(`${API_URL}/v1/videos/${videoId}/comments`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ body, parent_id: parentId ?? null }),
    }).catch(() => null);
    setPending(false);

    if (!response || !response.ok) {
      setError(
        response?.status === 422
          ? "That comment could not be posted. Check it is not empty."
          : "The comment did not post. Try again.",
      );
      return;
    }

    setBody("");
    onDone?.();
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="mt-3">
      <label htmlFor={`composer-${parentId ?? "root"}`} className="sr-only">
        {placeholder}
      </label>
      <textarea
        id={`composer-${parentId ?? "root"}`}
        value={body}
        onChange={(event) => setBody(event.target.value)}
        placeholder={placeholder}
        rows={3}
        className={cn(
          "w-full resize-y rounded-(--radius-sm) border border-rule bg-canvas px-3 py-2",
          "text-(length:--step-0) text-ink placeholder:text-muted",
          "outline-none transition-colors focus:border-muted",
        )}
      />

      {error && (
        <p role="alert" className="mt-2 text-(length:--step--1) text-danger">
          {error}
        </p>
      )}

      <div className="mt-2 flex items-center gap-2">
        <button
          type="submit"
          disabled={pending || body.trim().length === 0}
          className={cn(
            "rounded-(--radius-sm) bg-ink px-3 py-1.5",
            "text-(length:--step--1) font-medium text-canvas",
            "transition-opacity hover:opacity-90 disabled:opacity-40",
          )}
        >
          {/* Same verb throughout the flow (§7.6). */}
          {pending ? "Posting…" : "Post"}
        </button>
        {onDone && (
          <button
            type="button"
            onClick={onDone}
            className="text-(length:--step--1) text-muted hover:text-ink"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

export function Comments({
  videoId,
  comments,
  isSignedIn,
}: {
  videoId: string;
  comments: Comment[];
  isSignedIn: boolean;
}) {
  const [replyingTo, setReplyingTo] = useState<string | null>(null);

  return (
    <section aria-labelledby="comments-heading" className="mt-10">
      <h2 id="comments-heading" className="text-(length:--step-2)">
        {comments.length === 0
          ? "Comments"
          : `${comments.length} comment${comments.length === 1 ? "" : "s"}`}
      </h2>

      {isSignedIn ? (
        <Composer videoId={videoId} placeholder="Add a comment" />
      ) : (
        <p className="mt-3 rounded-(--radius-md) border border-rule bg-surface p-4 text-(length:--step--1) text-muted">
          <Link href="/login" className="font-medium text-ink underline underline-offset-4">
            Sign in
          </Link>{" "}
          to join the conversation.
        </p>
      )}

      {comments.length === 0 ? (
        <p className="mt-8 text-(length:--step--1) text-muted">
          No comments yet. Say the first thing.
        </p>
      ) : (
        <ol className="mt-8 space-y-7">
          {comments.map((comment) => (
            <li key={comment.id}>
              <CommentBody
                comment={comment}
                onReply={isSignedIn ? () => setReplyingTo(comment.id) : undefined}
              />

              {replyingTo === comment.id && (
                <div className="ml-11">
                  <Composer
                    videoId={videoId}
                    parentId={comment.id}
                    placeholder={`Reply to ${comment.author.display_name}`}
                    onDone={() => setReplyingTo(null)}
                  />
                </div>
              )}

              {comment.replies.length > 0 && (
                <ol className="ml-11 mt-5 space-y-5">
                  {comment.replies.map((reply) => (
                    <li key={reply.id}>
                      {/* No reply control here — one level is the shape. */}
                      <CommentBody comment={reply} />
                    </li>
                  ))}
                </ol>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
