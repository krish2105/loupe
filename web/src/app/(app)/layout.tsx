import { AppShell, type ShellUser } from "@/components/shell/AppShell";
import { getSubscribedChannels } from "@/lib/collections";
import { getAccessToken, getCurrentUser } from "@/lib/supabase/server";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const [user, token] = await Promise.all([getCurrentUser(), getAccessToken()]);
  const channels = await getSubscribedChannels(token);

  const shellUser: ShellUser | null = user?.email
    ? { email: user.email, initial: user.email[0]!.toUpperCase() }
    : null;

  return (
    <AppShell user={shellUser} channels={channels?.items ?? []}>
      {children}
    </AppShell>
  );
}
