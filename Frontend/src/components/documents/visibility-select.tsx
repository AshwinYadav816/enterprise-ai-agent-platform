"use client";

import { Lock, Shield, Users } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { VISIBILITY_LABEL, visibilityOptions, type UserRole } from "@/lib/documents";

const ICON = { employee: Users, manager: Shield, admin: Lock } as const;

/** Who can see an uploaded document. Levels above the user's own role are not offered. */
export function VisibilitySelect({
  role,
  value,
  onChange,
  id,
  disabled,
}: {
  role: UserRole;
  value: UserRole;
  onChange: (value: UserRole) => void;
  id?: string;
  disabled?: boolean;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as UserRole)} disabled={disabled}>
      <SelectTrigger id={id} className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {visibilityOptions(role).map((level) => {
          const Icon = ICON[level];
          return (
            <SelectItem key={level} value={level}>
              <Icon className="text-muted-foreground" aria-hidden />
              {VISIBILITY_LABEL[level]}
            </SelectItem>
          );
        })}
      </SelectContent>
    </Select>
  );
}

export function VisibilityBadge({ visibility }: { visibility: UserRole }) {
  const Icon = ICON[visibility];
  return (
    <Badge variant={visibility === "employee" ? "outline" : "info"}>
      <Icon aria-hidden /> {VISIBILITY_LABEL[visibility]}
    </Badge>
  );
}
