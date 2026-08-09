import { AppShell, type ShellUser } from "@/components/shell/AppShell";
import { getNotifications, getSubscribedChannels } from "@/lib/collections";
import { getAccessToken, getCurrentUser } from "@/lib/supabase/server";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const [user, token] = await Promise.all([getCurrentUser(), getAccessToken()]);
  const [channels, notifications] = await Promise.all([
    getSubscribedChannels(token),
    getNotifications(token),
  ]);

  const shellUser: ShellUser | null = user?.email
    ? { email: user.email, initial: user.email[0]!.toUpperCase() }
    : null;

  return (
    <AppShell
      user={shellUser}
      channels={channels?.items ?? []}
      unread={notifications?.unread ?? 0}
    >
      {children}
    </AppShell>
  );
}
