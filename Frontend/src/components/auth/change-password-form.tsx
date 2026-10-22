"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { FormAlert, handleFormError, PasswordField } from "@/components/auth/form-fields";
import { Button } from "@/components/ui/button";
import { HOME_PATH, safeNext } from "@/lib/redirects";
import { useAuth } from "@/providers/auth-provider";

export const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Enter your current password"),
    new_password: z
      .string()
      .min(8, "Use at least 8 characters")
      .max(128, "Use at most 128 characters"),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, {
    path: ["confirm"],
    message: "Passwords don't match",
  })
  .refine((v) => v.new_password !== v.current_password, {
    path: ["new_password"],
    message: "Choose a password different from the current one",
  });

type Values = z.infer<typeof changePasswordSchema>;

export function ChangePasswordForm() {
  const { user, changePassword, logout } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const forced = user?.must_change_password ?? false;
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });

  const onSubmit = handleSubmit(async ({ current_password, new_password }) => {
    try {
      await changePassword(current_password, new_password);
      toast.success("Password changed. Other devices have been signed out.");
      router.replace(next ?? HOME_PATH);
    } catch (error) {
      handleFormError(error, setError, ["current_password", "new_password"]);
    }
  });

  return (
    <div className="space-y-6">
      <div className="space-y-1.5">
        <h1 className="type-title">{forced ? "Choose a new password" : "Change password"}</h1>
        <p className="text-muted-foreground">
          {forced
            ? "You signed in with a temporary password. Pick your own to continue."
            : "All other devices will be signed out."}
        </p>
      </div>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <PasswordField
          label={forced ? "Temporary password" : "Current password"}
          autoComplete="current-password"
          autoFocus
          error={errors.current_password?.message}
          {...register("current_password")}
        />
        <PasswordField
          label="New password"
          autoComplete="new-password"
          description="At least 8 characters."
          error={errors.new_password?.message}
          {...register("new_password")}
        />
        <PasswordField
          label="Confirm new password"
          autoComplete="new-password"
          error={errors.confirm?.message}
          {...register("confirm")}
        />
        <FormAlert message={errors.root?.server?.message} />
        <Button type="submit" size="lg" className="w-full" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="animate-spin" aria-hidden />}
          {isSubmitting ? "Saving…" : "Save password"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        {forced ? "Not you? " : "Changed your mind? "}
        <button
          type="button"
          onClick={() => (forced ? void logout() : router.back())}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          {forced ? "Log out" : "Go back"}
        </button>
      </p>
    </div>
  );
}
