import type { Metadata } from "next";
import Link from "next/link";

import { Wordmark } from "@/components/common/wordmark";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <main
      id="main"
      className="flex min-h-svh flex-col items-center justify-center gap-6 px-4 text-center"
    >
      <Wordmark />
      <div className="space-y-2">
        <p className="type-eyebrow text-muted-foreground">Error 404</p>
        <h1 className="type-display">We couldn&apos;t find that page</h1>
        <p className="max-w-md text-muted-foreground">
          The link may be old, or the page may have moved.
        </p>
      </div>
      <Button asChild>
        <Link href="/">Go to the start page</Link>
      </Button>
    </main>
  );
}
