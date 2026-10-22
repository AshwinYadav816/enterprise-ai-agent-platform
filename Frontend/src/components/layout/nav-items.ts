import {
  Activity,
  FileText,
  History,
  LayoutDashboard,
  Mail,
  MessageSquare,
  NotebookPen,
  Settings,
  type LucideIcon,
  UserCog,
  Users,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Only this exact path is active (e.g. /admin must not light up on /admin/users). */
  exact?: boolean;
};

export const MAIN_NAV: NavItem[] = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/meetings", label: "Meetings", icon: Users },
  { href: "/reports", label: "Reports", icon: NotebookPen },
  { href: "/email", label: "Email", icon: Mail },
  { href: "/history", label: "History", icon: History },
];

export const ADMIN_NAV: NavItem[] = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/admin/users", label: "Users", icon: UserCog },
  { href: "/admin/activity", label: "Activity", icon: Activity },
];

export const SETTINGS_NAV: NavItem = { href: "/settings", label: "Settings", icon: Settings };

export function isActive(item: NavItem, pathname: string): boolean {
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

/** Title for the mobile top bar: the nav item that owns the current path. */
export function titleForPath(pathname: string): string {
  const items = [...ADMIN_NAV, ...MAIN_NAV, SETTINGS_NAV];
  const match = items.find((item) => isActive(item, pathname));
  if (!match) return "";
  return ADMIN_NAV.includes(match) && match.label === "Dashboard" ? "Admin" : match.label;
}
