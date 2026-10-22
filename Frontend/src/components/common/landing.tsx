"use client";

import { FileSearch, FileText, Mail, NotebookPen, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { Wordmark } from "@/components/common/wordmark";
import { FullPageSkeleton } from "@/components/layout/auth-guard";
import { Button } from "@/components/ui/button";
import { postLoginPath } from "@/lib/redirects";
import { useAuth } from "@/providers/auth-provider";

const AGENTS = [
  {
    icon: FileSearch,
    name: "Research",
    text: "Answers from your documents, with sources you can open.",
  },
  { icon: Users, name: "Meetings", text: "Summaries, decisions and action items with owners." },
  { icon: NotebookPen, name: "Reports", text: "Weekly, monthly, sprint and project reports." },
  { icon: Mail, name: "Email", text: "Drafts, rewrites and summaries in the right tone." },
  { icon: FileText, name: "Documents", text: "Key points and questions to ask about any file." },
];

/** "/": a short public page for visitors; signed-in users go straight to the app. */
export function Landing() {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated" && user) router.replace(postLoginPath(user));
  }, [status, user, router]);

  if (status !== "anonymous") return <FullPageSkeleton />;

  return (
    <div className="flex min-h-svh flex-col">
      <header className="mx-auto flex w-full max-w-[1200px] items-center justify-between gap-4 px-4 py-5 md:px-8">
        <Wordmark />
        <nav aria-label="Account" className="flex items-center gap-2">
          <Button asChild variant="ghost">
            <Link href="/login">Sign in</Link>
          </Button>
          <Button asChild className="hidden sm:inline-flex">
            <Link href="/register">Create workspace</Link>
          </Button>
        </nav>
      </header>

      <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-4 md:px-8">
        <section className="max-w-3xl py-14 md:py-24">
          <p className="type-eyebrow text-muted-foreground">Enterprise AI agents</p>
          <h1 className="mt-3 font-serif text-[2.5rem] leading-[1.1] font-semibold text-balance md:text-6xl">
            Your company&apos;s knowledge, ready to work for you.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">
            Upload your policies, plans and reports, then ask questions and get answers that cite
            the source. Hand off the routine writing too: meeting notes, reports and emails, drafted
            in seconds and shared only with the people who should see them.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/register">Create workspace</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/login">Sign in</Link>
            </Button>
          </div>
        </section>

        <section aria-labelledby="agents-title" className="border-t py-12">
          <h2 id="agents-title" className="type-title">
            Five agents, one assistant
          </h2>
          <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {AGENTS.map(({ icon: Icon, name, text }) => (
              <li key={name} className="rounded-lg border bg-card p-5">
                <Icon className="size-5 text-primary" aria-hidden />
                <h3 className="mt-3 font-serif text-lg font-semibold">{name}</h3>
                <p className="mt-1 type-small text-muted-foreground">{text}</p>
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="border-t">
        <p className="mx-auto w-full max-w-[1200px] px-4 py-6 type-small text-muted-foreground md:px-8">
          Enterprise AI Agent Platform · role-based access · answers cite their sources
        </p>
      </footer>
    </div>
  );
}
