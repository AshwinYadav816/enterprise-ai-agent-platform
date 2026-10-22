"use client";

import { AlertCircle, Eye, EyeOff } from "lucide-react";
import { useId, useState } from "react";
import type { FieldValues, Path, UseFormSetError } from "react-hook-form";

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ApiError, errorMessage } from "@/lib/api/errors";

type TextFieldProps = React.ComponentProps<"input"> & {
  label: string;
  error?: string;
  description?: string;
};

/** Label + input + error, wired for accessibility. Spread react-hook-form's `register(name)`. */
export function TextField({ label, error, description, id, ...inputProps }: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const describedBy = [error && `${inputId}-error`, description && `${inputId}-hint`]
    .filter(Boolean)
    .join(" ");
  return (
    <Field data-invalid={!!error || undefined}>
      <FieldLabel htmlFor={inputId}>{label}</FieldLabel>
      <Input
        id={inputId}
        aria-invalid={!!error || undefined}
        aria-describedby={describedBy || undefined}
        {...inputProps}
      />
      {description && !error && (
        <FieldDescription id={`${inputId}-hint`}>{description}</FieldDescription>
      )}
      {error && <FieldError id={`${inputId}-error`}>{error}</FieldError>}
    </Field>
  );
}

/** TextField for passwords with a show/hide toggle. */
export function PasswordField({ label, error, description, id, ...inputProps }: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const [visible, setVisible] = useState(false);
  const describedBy = [error && `${inputId}-error`, description && `${inputId}-hint`]
    .filter(Boolean)
    .join(" ");
  return (
    <Field data-invalid={!!error || undefined}>
      <FieldLabel htmlFor={inputId}>{label}</FieldLabel>
      <div className="relative">
        <Input
          id={inputId}
          type={visible ? "text" : "password"}
          className="pr-10"
          aria-invalid={!!error || undefined}
          aria-describedby={describedBy || undefined}
          {...inputProps}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-lg text-muted-foreground transition-colors duration-150 hover:text-foreground"
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </button>
      </div>
      {description && !error && (
        <FieldDescription id={`${inputId}-hint`}>{description}</FieldDescription>
      )}
      {error && <FieldError id={`${inputId}-error`}>{error}</FieldError>}
    </Field>
  );
}

/** The server's message for the whole form (wrong password, rate limit, offline, …). */
export function FormAlert({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive-tint px-3 py-2.5 text-sm text-destructive"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}

/**
 * Show a failed submit: 422 field details go under their fields (when the form has them),
 * everything else becomes the form-level message in `errors.root.server`.
 */
export function handleFormError<T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: readonly Path<T>[],
): void {
  if (error instanceof ApiError) {
    const placed = error.details.filter((d) => (fields as readonly string[]).includes(d.field));
    placed.forEach((d) => setError(d.field as Path<T>, { type: "server", message: d.message }));
    if (placed.length > 0 && placed.length === error.details.length) return;
  }
  setError("root.server", { type: "server", message: errorMessage(error) });
}
