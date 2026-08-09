import type { Metadata } from "next";
import Link from "next/link";
import { MarkRead } from "@/components/notifications/MarkRead";
import { Avatar } from "@/components/shell/Avatar";
import { getNotifications, type Notification } from "@/lib/collections";
import { getAccessToken } from "@/lib/supabase/server";
import { cn, formatAge } from "@/lib/utils";

export const metadata: Metadata = { title: "Notifications" };
export const dynamic = "force-dynamic";

/**
 * What each kind of notification actually says.
 *
 * Written per §7.6: the sentence names the person or channel that acted and
 * what they did, in that order, because that is the order someone scanning the
 * list reads it in. A generic "you have a new notification" would make the list
 * unreadable without opening every row.
 */
function describe(item: Notification) {
  const who = item.kind === "reply" ? item.actor_name : item.channel_name;
  const what = item.kind === "reply" ? "replied on" : "posted";

  return {
    who: who ?? "Someone",
    what,
    title: item.target_title ?? "a talk",
  };
}

export default async function NotificationsPage() {
  const token = await getAccessToken();
  const data = await getNotifications(token);

  if (!token) {
    return (
      <div className="mx-auto max-w-[46ch] py-24 text-center">
        <h1 className="text-(length:--step-3)">Notifications</h1>
        <p className="mt-3 text-pretty text-(length:--step--1) text-muted">
          This is yours, so it needs an account.
        </p>
        <Link
          href="/login"
          className={cn(
            "mt-6 inline-block rounded-(--radius-pill) bg-brand px-4 py-2",
            "text-(length:--step--1) font-medium text-white hover:opacity-90",
          )}
        >
          Sign in
        </Link>
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <div className="mx-auto max-w-[720px] py-6">
      <MarkRead unread={data?.unread ?? 0} />
      <h1 className="text-(length:--step-3)">Notifications</h1>

      {items.length === 0 ? (
        <div className="py-24 text-center">
          <p className="text-(length:--step-1)">Nothing new</p>
          <p className="mx-auto mt-2 max-w-[42ch] text-pretty text-(length:--step--1) text-muted">
            Follow a channel and you will hear about its new talks here.
          </p>
        </div>
      ) : (
        <ol className="mt-6 divide-y divide-rule">
          {items.map((item) => {
            const { who, what, title } = describe(item);

            return (
            <li key={item.id}>
              <Link
                href={`/watch/${item.target_id}`}
                className={cn(
                  "flex items-start gap-3 py-4 transition-colors hover:bg-surface",
                  !item.read && "bg-brand-faint",
                )}
              >
                <Avatar name={who} size={36} />
                <div className="min-w-0 flex-1">
                  <p className="text-(length:--step--1)">
                    <span className="font-medium">{who}</span> {what} {title}
                  </p>
                  <p className="mt-1 text-(length:--step--2) text-muted">
                    {formatAge(item.created_at)}
                  </p>
                </div>
                {!item.read && (
                  <span
                    aria-label="Unread"
                    className="mt-2 size-2 shrink-0 rounded-full bg-brand"
                  />
                )}
              </Link>
            </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
