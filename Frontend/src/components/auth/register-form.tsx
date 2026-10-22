"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";

import {
  FormAlert,
  handleFormError,
  PasswordField,
  TextField,
} from "@/components/auth/form-fields";
import { Button } from "@/components/ui/button";
import { safeNext } from "@/lib/redirects";
import { useAuth } from "@/providers/auth-provider";

// Limits mirror the backend (RegisterRequest): names 1–200, password 8–128.
export const registerSchema = z
  .object({
    org_name: z.string().trim().min(1, "Enter your organization's name").max(200),
    full_name: z.string().trim().min(1, "Enter your full name").max(200),
    email: z.email("Enter a valid email address"),
    password: z.string().min(8, "Use at least 8 characters").max(128, "Use at most 128 characters"),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Passwords don't match",
  });

type Values = z.infer<typeof registerSchema>;

export function RegisterForm() {
  const { register: createAccount } = useAuth();
  const next = safeNext(useSearchParams().get("next"));
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(registerSchema),
    defaultValues: { org_name: "", full_name: "", email: "", password: "", confirm: "" },
  });

  const onSubmit = handleSubmit(async ({ org_name, full_name, email, password }) => {
    try {
      // you become the admin of the new workspace
      await createAccount({ org_name, full_name, email, password });
    } catch (error) {
      handleFormError(error, setError, ["org_name", "full_name", "email", "password"]);
    }
  });

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <h1 className="type-title">Create a workspace</h1>
        <p className="text-muted-foreground">You&apos;ll be its admin and can invite your team.</p>
      </div>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Organization name"
          autoComplete="organization"
          autoFocus
          error={errors.org_name?.message}
          {...register("org_name")}
        />
        <TextField
          label="Full name"
          autoComplete="name"
          error={errors.full_name?.message}
          {...register("full_name")}
        />
        <TextField
          label="Work email"
          type="email"
          autoComplete="email"
          error={errors.email?.message}
          {...register("email")}
        />
        <PasswordField
          label="Password"
          autoComplete="new-password"
          description="At least 8 characters."
          error={errors.password?.message}
          {...register("password")}
        />
        <PasswordField
          label="Confirm password"
          autoComplete="new-password"
          error={errors.confirm?.message}
          {...register("confirm")}
        />
        <FormAlert message={errors.root?.server?.message} />
        <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
          {isSubmitting ? "Creating workspace…" : "Create workspace"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link
          href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}
