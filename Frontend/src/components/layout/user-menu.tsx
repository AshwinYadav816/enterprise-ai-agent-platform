"use client";

import { ChevronsUpDown, LogOut, Settings } from "lucide-react";
import Link from "next/link";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { User } from "@/lib/api/auth";
import { cn } from "@/lib/utils";
import { useAuth } from "@/providers/auth-provider";

const ROLE_LABEL: Record<User["role"], string> = {
  admin: "Admin",
  manager: "Manager",
  employee: "Employee",
};

export function RoleBadge({ role, className }: { role: User["role"]; className?: string }) {
  const variant = role === "admin" ? "default" : role === "manager" ? "info" : "secondary";
  return (
    <Badge variant={variant} className={className}>
      {ROLE_LABEL[role]}
    </Badge>
  );
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0][0], parts.at(-1)![0]] : [parts[0]?.[0] ?? "?"];
  return letters.join("").toUpperCase();
}

export function UserMenu({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex w-full items-center gap-3 rounded-md p-1.5 text-left transition-colors duration-150 outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background data-[state=open]:bg-accent",
          collapsed && "justify-center",
        )}
        aria-label={`Account menu for ${user.full_name}`}
      >
        <Avatar className="size-8">
          <AvatarFallback className="bg-blue-tint text-xs font-semibold text-primary">
            {initials(user.full_name)}
          </AvatarFallback>
        </Avatar>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">{user.full_name}</span>
              <RoleBadge role={user.role} className="mt-0.5" />
            </span>
            <ChevronsUpDown className="size-4 text-muted-foreground" aria-hidden />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent side={collapsed ? "right" : "top"} align="start" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate text-sm font-medium text-foreground">
            {user.full_name}
          </span>
          <span className="block truncate text-xs text-muted-foreground">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/settings" onClick={onNavigate}>
            <Settings /> Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => {
            onNavigate?.();
            void logout();
          }}
        >
          <LogOut /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
