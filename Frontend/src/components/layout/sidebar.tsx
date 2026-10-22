"use client";

import { PanelLeftClose, PanelLeftOpen, Plus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Wordmark } from "@/components/common/wordmark";
import { ADMIN_NAV, isActive, MAIN_NAV, type NavItem } from "@/components/layout/nav-items";
import { UserMenu } from "@/components/layout/user-menu";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";

type SidebarProps = {
  collapsed: boolean;
  onToggle: () => void;
};

/** Desktop sidebar (≥ 1024 px). Collapses to icons with tooltips. */
export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-svh shrink-0 flex-col border-r bg-sidebar transition-[width] duration-200 ease-out lg:flex",
        collapsed ? "w-16" : "w-64",
      )}
    >
      <div
        className={cn(
          "flex h-16 items-center px-4",
          collapsed ? "justify-center px-2" : "justify-between",
        )}
      >
        {!collapsed && (
          <Link href="/chat" aria-label="Agent Platform home" className="rounded-sm">
            <Wordmark className="text-xl" />
          </Link>
        )}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={onToggle}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">{collapsed ? "Expand" : "Collapse"}</TooltipContent>
        </Tooltip>
      </div>
      <SidebarNav collapsed={collapsed} />
    </aside>
  );
}

/** Sidebar body, shared by the desktop aside and the mobile sheet. */
export function SidebarNav({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const { user } = useAuth();
  const pathname = usePathname();

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className={cn("px-3 pb-3", collapsed && "px-2")}>
        <NewChatButton collapsed={collapsed} onNavigate={onNavigate} />
      </div>

      <nav aria-label="Main" className="flex-1 overflow-y-auto px-3 pb-3">
        <NavList
          items={MAIN_NAV}
          pathname={pathname}
          collapsed={collapsed}
          onNavigate={onNavigate}
        />
        {user?.role === "admin" && (
          <div className="mt-6">
            {collapsed ? (
              <div className="mx-2 mb-2 border-t" aria-hidden />
            ) : (
              <p className="mb-2 px-3 type-eyebrow text-muted-foreground">Admin</p>
            )}
            <NavList
              items={ADMIN_NAV}
              pathname={pathname}
              collapsed={collapsed}
              onNavigate={onNavigate}
              label="Admin"
            />
          </div>
        )}
      </nav>

      <div className={cn("border-t p-3", collapsed && "p-2")}>
        <UserMenu collapsed={collapsed} onNavigate={onNavigate} />
      </div>
    </div>
  );
}

function NewChatButton({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Button asChild size="icon" className="mx-auto flex">
            <Link href="/chat" onClick={onNavigate} aria-label="New chat">
              <Plus />
            </Link>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">New chat</TooltipContent>
      </Tooltip>
    );
  }
  return (
    <Button asChild className="w-full justify-start">
      <Link href="/chat" onClick={onNavigate}>
        <Plus /> New chat
      </Link>
    </Button>
  );
}

function NavList({
  items,
  pathname,
  collapsed,
  onNavigate,
  label,
}: {
  items: NavItem[];
  pathname: string;
  collapsed: boolean;
  onNavigate?: () => void;
  label?: string;
}) {
  return (
    <ul className="space-y-0.5" aria-label={label}>
      {items.map((item) => (
        <li key={item.href}>
          <NavLink
            item={item}
            active={isActive(item, pathname)}
            collapsed={collapsed}
            onNavigate={onNavigate}
          />
        </li>
      ))}
    </ul>
  );
}

function NavLink({
  item,
  active,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={cn(
        "relative flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors duration-150",
        collapsed && "justify-center px-0",
        active
          ? // active: blue-tint + blue text + the 3px coral bar (coral rule)
            "bg-blue-tint font-medium text-primary before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-coral"
          : "text-foreground hover:bg-accent hover:text-accent-foreground",
      )}
    >
      <Icon className={cn("size-4 shrink-0", !active && "text-muted-foreground")} aria-hidden />
      {!collapsed && <span className="truncate">{item.label}</span>}
    </Link>
  );

  if (!collapsed) return link;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{item.label}</TooltipContent>
    </Tooltip>
  );
}
