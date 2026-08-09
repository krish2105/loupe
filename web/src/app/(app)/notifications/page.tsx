import type { Metadata } from "next";
import Link from "next/link";
import { Avatar } from "@/components/shell/Avatar";
import { API_URL } from "@/lib/api";
import { getAccessToken } from "@/lib/supabase/server";
import { cn, formatAge } from "@/lib/utils";

export const metadata: Metadata = { title: "Notifications" };
export const dynamic = "force-dynamic";

type Notification = {
  id: string;
  kind: string;
  target_id: string;
  target_title: string | null;
  channel_name: string | null;
  created_at: string;
  read: boolean;
};

async function getNotifications(token: string | null) {
  if (!API_URL || !token) return null;
  try {
    const response = await fetch(`${API_URL}/v1/me/notifications`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) return null;
    return (await response.json()) as { items: Notification[]; unread: number };
  } catch {
    return null;
  }
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
          {items.map((item) => (
            <li key={item.id}>
              <Link
                href={`/watch/${item.target_id}`}
                className={cn(
                  "flex items-start gap-3 py-4 transition-colors hover:bg-surface",
                  !item.read && "bg-brand-faint",
                )}
              >
                <Avatar name={item.channel_name ?? "?"} size={36} />
                <div className="min-w-0 flex-1">
                  <p className="text-(length:--step--1)">
                    <span className="font-medium">{item.channel_name}</span>{" "}
                    posted {item.target_title}
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
          ))}
        </ol>
      )}
    </div>
  );
}
