import { MiniPlayer } from "@/components/audio/MiniPlayer";
import { QueueProvider } from "@/components/audio/QueueContext";
import { PlayerProvider } from "@/components/player/PlayerContext";
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

  /*
    The player store lives here rather than on the video page, which is what
    makes audio survive navigation (ADR 0003).

    One store for the whole app, so opening a talk attaches the video element
    and takes playback over from any audio that was playing. That is a real
    consequence and it is the right one: two independent players both making
    sound is worse than one taking over, and a second store would have meant
    two things that both believe they are the source of playback truth.
  */
  return (
    <PlayerProvider>
      <QueueProvider>
        <AppShell
          user={shellUser}
          channels={channels?.items ?? []}
          unread={notifications?.unread ?? 0}
        >
          {children}
        </AppShell>
        <MiniPlayer />
      </QueueProvider>
    </PlayerProvider>
  );
}
