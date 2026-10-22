"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { KeyRound, Loader2, UserPlus } from "lucide-react";
import { useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { FormAlert, handleFormError, TextField } from "@/components/auth/form-fields";
import { CopyButton } from "@/components/chat/result-card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ROLE_LABEL, useCreateUser, type CreatedUser, type UserRole } from "@/lib/hooks/use-admin";

const schema = z.object({
  full_name: z.string().trim().min(1, "Enter their full name").max(200),
  email: z.email("Enter a valid email address"),
  role: z.enum(["employee", "manager", "admin"]),
});
type Values = z.infer<typeof schema>;

/** Add a user with a temporary password, shown exactly once. */
export function CreateUserDialog() {
  const [open, setOpen] = useState(false);
  const [created, setCreated] = useState<CreatedUser | null>(null);
  const create = useCreateUser();
  const roleId = useId();
  const {
    control,
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", role: "employee" },
  });

  const onOpenChange = (next: boolean) => {
    setOpen(next);
    if (!next) {
      // forget the password as soon as the dialog closes: it can't be shown again
      setCreated(null);
      reset();
      create.reset();
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    try {
      setCreated(await create.mutateAsync(values));
    } catch (error) {
      handleFormError(error, setError, ["full_name", "email", "role"]);
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <UserPlus /> Add user
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        {created ? (
          <>
            <DialogHeader>
              <DialogTitle>{created.user.full_name} can sign in now</DialogTitle>
              <DialogDescription>
                Give them their email ({created.user.email}) and this temporary password.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-3 rounded-lg border border-warning/30 bg-warning-tint p-4">
              <p className="flex items-center gap-1.5 type-eyebrow text-warning">
                <KeyRound className="size-3.5" aria-hidden /> Temporary password
              </p>
              <div className="flex items-center justify-between gap-2 rounded-md border bg-card px-3 py-2">
                <code
                  className="font-mono text-base break-all select-all"
                  aria-label="Temporary password"
                >
                  {created.temporary_password}
                </code>
                <CopyButton text={created.temporary_password} label="Copy" className="shrink-0" />
              </div>
              <p className="type-small text-foreground">
                Share this securely; the user must change it on first login. It won&apos;t be shown
                again.
              </p>
            </div>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </DialogFooter>
          </>
        ) : (
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            <DialogHeader>
              <DialogTitle>Add a user</DialogTitle>
              <DialogDescription>
                They get a temporary password and choose their own at first sign-in.
              </DialogDescription>
            </DialogHeader>
            <TextField
              label="Full name"
              autoComplete="off"
              error={errors.full_name?.message}
              {...register("full_name")}
            />
            <TextField
              label="Work email"
              type="email"
              autoComplete="off"
              error={errors.email?.message}
              {...register("email")}
            />
            <Field>
              <FieldLabel htmlFor={roleId}>Role</FieldLabel>
              <Controller
                control={control}
                name="role"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={(v) => field.onChange(v as UserRole)}>
                    <SelectTrigger id={roleId} className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(ROLE_LABEL) as UserRole[]).reverse().map((role) => (
                        <SelectItem key={role} value={role}>
                          {ROLE_LABEL[role]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <FormAlert message={errors.root?.server?.message} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={create.isPending}>
                {create.isPending && <Loader2 className="animate-spin" aria-hidden />}
                {create.isPending ? "Adding…" : "Add user"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
