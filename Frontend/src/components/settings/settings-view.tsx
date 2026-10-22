"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { changePasswordSchema } from "@/components/auth/change-password-form";
import {
  FormAlert,
  handleFormError,
  PasswordField,
  TextField,
} from "@/components/auth/form-fields";
import { RoleBadge } from "@/components/layout/user-menu";
import { PageHeader } from "@/components/common/page-header";
import { SubmitLabel } from "@/components/tools/tool-layout";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/errors";
import { formatDateTime } from "@/lib/format";
import { useAuth } from "@/providers/auth-provider";

export function SettingsView() {
  return (
    <div className="space-y-8">
      <PageHeader eyebrow="Account" title="Settings" description="Your profile and password." />
      <div className="grid max-w-3xl gap-6">
        <ProfileSection />
        <PasswordSection />
      </div>
    </div>
  );
}

function Section({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-card p-5 md:p-6">
      <h2 className="type-title">{title}</h2>
      <p className="mt-1 text-muted-foreground">{description}</p>
      <div className="mt-5">{children}</div>
    </section>
  );
}

const profileSchema = z.object({
  full_name: z.string().trim().min(1, "Enter your full name").max(200),
});

function ProfileSection() {
  const { user, refreshUser } = useAuth();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting, isDirty },
    reset,
  } = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    values: { full_name: user?.full_name ?? "" },
  });
  if (!user) return null;

  const onSubmit = handleSubmit(async ({ full_name }) => {
    try {
      unwrap(await api.PATCH("/api/v1/users/me", { body: { full_name } }));
      const me = await refreshUser();
      reset({ full_name: me.full_name });
      toast.success("Profile saved");
    } catch (error) {
      handleFormError(error, setError, ["full_name"]);
    }
  });

  return (
    <Section title="Profile" description="How you appear to your colleagues.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <TextField
          label="Full name"
          autoComplete="name"
          error={errors.full_name?.message}
          {...register("full_name")}
        />
        <Field>
          <FieldLabel htmlFor="settings-email">Email</FieldLabel>
          <Input
            id="settings-email"
            value={user.email}
            readOnly
            aria-readonly
            className="bg-muted"
          />
          <FieldDescription>Ask an admin if your email needs to change.</FieldDescription>
        </Field>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
          <span className="flex items-center gap-2">
            <span className="text-muted-foreground">Role</span> <RoleBadge role={user.role} />
          </span>
          {user.last_login_at && (
            <span className="text-muted-foreground">
              Last sign-in {formatDateTime(user.last_login_at)}
            </span>
          )}
        </div>
        <FormAlert message={errors.root?.server?.message} />
        <Button type="submit" disabled={isSubmitting || !isDirty}>
          <SubmitLabel pending={isSubmitting} idle="Save profile" busy="Saving…" />
        </Button>
      </form>
    </Section>
  );
}

function PasswordSection() {
  const { changePassword } = useAuth();
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof changePasswordSchema>>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm: "" },
  });

  const onSubmit = handleSubmit(async ({ current_password, new_password }) => {
    try {
      await changePassword(current_password, new_password);
      reset();
      toast.success("Password changed. Other devices have been signed out.");
    } catch (error) {
      handleFormError(error, setError, ["current_password", "new_password"]);
    }
  });

  return (
    <Section title="Password" description="Changing it signs you out on every other device.">
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        <PasswordField
          label="Current password"
          autoComplete="current-password"
          error={errors.current_password?.message}
          {...register("current_password")}
        />
        <div className="grid gap-4 sm:grid-cols-2">
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
        </div>
        <FormAlert message={errors.root?.server?.message} />
        <Button type="submit" disabled={isSubmitting}>
          <SubmitLabel pending={isSubmitting} idle="Change password" busy="Saving…" />
        </Button>
      </form>
    </Section>
  );
}
