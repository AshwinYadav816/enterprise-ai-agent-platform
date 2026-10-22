import { AuthGuard, ContentSkeleton } from "@/components/layout/auth-guard";

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <AuthGuard adminOnly fallback={<ContentSkeleton />}>
      {children}
    </AuthGuard>
  );
}
