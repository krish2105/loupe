import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/supabase/server";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage() {
  // Someone already signed in has no business on this page.
  if (await getCurrentUser()) redirect("/");

  return <LoginForm />;
}
