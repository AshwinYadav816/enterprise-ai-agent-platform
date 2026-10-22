"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { api } from "@/lib/api/client";
import { unwrap } from "@/lib/api/errors";
import { keys } from "@/lib/api/keys";

export type PickedDoc = { id: string; filename: string };

/** Restrict the answer to some documents. Only READY ones are offered (the backend 409s others). */
export function DocPicker({
  value,
  onChange,
  disabled,
}: {
  value: PickedDoc[];
  onChange: (docs: PickedDoc[]) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const query = useQuery({
    queryKey: keys.documents.list({ status: "ready", picker: true }),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/documents", { params: { query: { status: "ready", limit: 100 } } }),
      ).items,
    enabled: open,
  });

  const selected = new Set(value.map((d) => d.id));
  const docs = (query.data ?? []).filter((d) =>
    d.filename.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  const toggle = (doc: PickedDoc) =>
    onChange(
      selected.has(doc.id)
        ? value.filter((d) => d.id !== doc.id)
        : [...value, { id: doc.id, filename: doc.filename }],
    );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" disabled={disabled} aria-label="Choose documents">
          <FileText />
          <span className="hidden sm:inline">Documents</span>
          {value.length > 0 && (
            <span className="rounded-full bg-primary px-1.5 text-[0.6875rem] text-primary-foreground">
              {value.length}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 gap-0 p-0">
        <div className="border-b p-2">
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter documents"
            aria-label="Filter documents"
            className="h-8"
          />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {query.isPending ? (
            <p className="flex items-center gap-2 p-3 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
            </p>
          ) : docs.length === 0 ? (
            <p className="p-3 text-sm text-muted-foreground">
              {query.data?.length ? (
                "No documents match."
              ) : (
                <>
                  No ready documents yet.{" "}
                  <Link href="/documents" className="font-medium text-primary underline">
                    Upload some
                  </Link>
                  .
                </>
              )}
            </p>
          ) : (
            <ul aria-label="Ready documents">
              {docs.map((doc) => (
                <li key={doc.id}>
                  <label className="flex cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-sm hover:bg-accent">
                    <Checkbox checked={selected.has(doc.id)} onCheckedChange={() => toggle(doc)} />
                    <span className="truncate">{doc.filename}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
        {value.length > 0 && (
          <div className="flex items-center justify-between border-t px-3 py-2 text-sm">
            <span className="text-muted-foreground">{value.length} selected</span>
            <Button variant="ghost" size="xs" onClick={() => onChange([])}>
              Clear
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
