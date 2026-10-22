import type { Metadata } from "next";

import { RegisterForm } from "@/components/auth/register-form";
import { GuestGuard } from "@/components/layout/auth-guard";

export const metadata: Metadata = { title: "Create a workspace" };

export default function RegisterPage() {
  return (
    <GuestGuard>
      <RegisterForm />
    </GuestGuard>
  );
}
