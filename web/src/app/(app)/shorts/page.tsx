import type { Metadata } from "next";
import { ShortsFeed } from "@/components/shorts/ShortsFeed";
import type { Short } from "@/components/shorts/ShortSlot";
import { API_URL } from "@/lib/api";

export const metadata: Metadata = { title: "Shorts" };
export const dynamic = "force-dynamic";

async function getShorts(): Promise<Short[]> {
  if (!API_URL) return [];
  try {
    const response = await fetch(`${API_URL}/v1/shorts?limit=12`, {
      cache: "no-store",
    });
    if (!response.ok) return [];
    return ((await response.json()) as { items: Short[] }).items;
  } catch {
    return [];
  }
}

export default async function ShortsPage() {
  return <ShortsFeed shorts={await getShorts()} />;
}
