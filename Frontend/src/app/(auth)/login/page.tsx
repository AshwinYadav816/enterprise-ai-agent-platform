import type { Metadata } from "next";

import { LoginForm } from "@/components/auth/login-form";
import { GuestGuard } from "@/components/layout/auth-guard";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <GuestGuard>
      <LoginForm />
    </GuestGuard>
  );
}
