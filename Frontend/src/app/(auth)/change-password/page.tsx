import type { Metadata } from "next";

import { ChangePasswordForm } from "@/components/auth/change-password-form";
import { AuthGuard, FormSkeleton } from "@/components/layout/auth-guard";

export const metadata: Metadata = { title: "Change password" };

export default function ChangePasswordPage() {
  return (
    <AuthGuard allowPasswordChange fallback={<FormSkeleton />}>
      <ChangePasswordForm />
    </AuthGuard>
  );
}
