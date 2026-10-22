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

const schema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

type Values = z.infer<typeof schema>;

export function LoginForm() {
  const { login } = useAuth();
  const next = safeNext(useSearchParams().get("next"));
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  // On success the GuestGuard sends the user on (password change, ?next= or /chat).
  const onSubmit = handleSubmit(async ({ email, password }) => {
    try {
      await login(email, password);
    } catch (error) {
      handleFormError(error, setError, ["email", "password"]);
    }
  });

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <h1 className="type-title">Sign in</h1>
        <p className="text-muted-foreground">Welcome back. Use your work email.</p>
      </div>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
          error={errors.email?.message}
          {...register("email")}
        />
        <PasswordField
          label="Password"
          autoComplete="current-password"
          error={errors.password?.message}
          {...register("password")}
        />
        <FormAlert message={errors.root?.server?.message} />
        <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
          {isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        New here?{" "}
        <Link
          href={next ? `/register?next=${encodeURIComponent(next)}` : "/register"}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Create a workspace
        </Link>
      </p>
    </div>
  );
}
