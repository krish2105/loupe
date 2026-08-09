import { AppShell, type ShellUser } from "@/components/shell/AppShell";
import { getCurrentUser } from "@/lib/supabase/server";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const user = await getCurrentUser();

  const shellUser: ShellUser | null = user?.email
    ? { email: user.email, initial: user.email[0]!.toUpperCase() }
    : null;

  return <AppShell user={shellUser}>{children}</AppShell>;
}
