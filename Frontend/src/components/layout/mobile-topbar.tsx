"use client";

import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Wordmark } from "@/components/common/wordmark";
import { titleForPath } from "@/components/layout/nav-items";
import { SidebarNav } from "@/components/layout/sidebar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";

/** Below 1024 px: menu button (opens the navigation sheet) and the page title. */
export function MobileTopbar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const title = titleForPath(pathname);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur lg:hidden">
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        aria-expanded={open}
      >
        <Menu />
      </Button>
      <span className="truncate font-serif text-lg font-semibold">
        {title || <Wordmark compact />}
      </span>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          side="left"
          className="flex w-72 flex-col gap-0 bg-sidebar p-0"
          aria-describedby={undefined}
        >
          <div className="flex h-16 items-center px-4">
            <SheetTitle asChild>
              <span>
                <Wordmark className="text-xl" />
              </span>
            </SheetTitle>
          </div>
          <SidebarNav onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
    </header>
  );
}
