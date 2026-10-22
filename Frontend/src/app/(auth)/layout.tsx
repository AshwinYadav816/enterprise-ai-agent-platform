import { FileSearch, ListChecks, ShieldCheck } from "lucide-react";

import { Wordmark } from "@/components/common/wordmark";

const FEATURES = [
  { icon: FileSearch, text: "Answers from your own documents, with sources you can open." },
  { icon: ListChecks, text: "Meeting summaries, reports and emails drafted in seconds." },
  { icon: ShieldCheck, text: "Role-based access: people only see what they're allowed to." },
];

/** Split screen on desktop (story left, form right); a single column on mobile. */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="grid min-h-svh lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <section className="hidden flex-col justify-between border-r bg-muted px-12 py-10 lg:flex">
        <Wordmark />
        <div className="max-w-md space-y-8">
          <h1 className="font-serif text-[2.5rem] leading-[1.15] font-semibold text-balance">
            Your company&apos;s knowledge, ready to work for you.
          </h1>
          <ul className="space-y-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3 text-muted-foreground">
                <Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="type-small text-muted-foreground">Enterprise AI Agent Platform</p>
      </section>

      <main className="flex flex-col items-center justify-center px-4 py-10 sm:px-8">
        <div className="mb-8 lg:hidden">
          <Wordmark />
        </div>
        <div className="w-full max-w-sm rounded-xl border bg-card p-6 sm:p-8">{children}</div>
      </main>
    </div>
  );
}
