"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { MobileTopbar } from "@/components/layout/mobile-topbar";
import { Sidebar } from "@/components/layout/sidebar";
import { cn } from "@/lib/utils";

/** Pages that manage their own height and scrolling (chat: composer pinned to the bottom). */
const FULL_BLEED = /^\/chat(\/|$)/;

/** Sidebar (desktop) or top bar + sheet (mobile) around the page content. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const fullBleed = FULL_BLEED.test(usePathname());

  return (
    <div className={cn("flex w-full", fullBleed ? "h-svh overflow-hidden" : "min-h-svh")}>
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <MobileTopbar />
        <main id="main" tabIndex={-1} className="min-h-0 flex-1 outline-none">
          {fullBleed ? (
            children
          ) : (
            <div className="mx-auto w-full max-w-[1200px] px-4 py-6 md:px-8 md:py-8">
              {children}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
