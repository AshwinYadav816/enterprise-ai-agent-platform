import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Loader2,
  Plus,
  Trash2,
  XCircle,
} from "lucide-react";

import { Wordmark } from "@/components/common/wordmark";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export const metadata: Metadata = { title: "Styleguide" };

// Dev-only reference page: every later screen inherits these tokens and patterns.
const COLORS: { group: string; tokens: [name: string, className: string, hex: string][] }[] = [
  {
    group: "Surfaces",
    tokens: [
      ["background", "bg-background", "#FAF6EE"],
      ["card / popover", "bg-card", "#FFFDF8"],
      ["muted / secondary", "bg-muted", "#F3EDE1"],
      ["border", "bg-border", "#E6DDCC"],
      ["input", "bg-input", "#D9CFBC"],
    ],
  },
  {
    group: "Ink & blue",
    tokens: [
      ["foreground", "bg-foreground", "#1A2233"],
      ["muted-foreground", "bg-muted-foreground", "#5B6475"],
      ["primary", "bg-primary", "#1D3461"],
      ["primary-hover", "bg-primary-hover", "#162849"],
      ["blue-tint / accent", "bg-blue-tint", "#E6ECF5"],
    ],
  },
  {
    group: "Coral (signature)",
    tokens: [
      ["coral", "bg-coral", "#E8664A"],
      ["coral-text", "bg-coral-text", "#B8452B"],
      ["coral-tint", "bg-coral-tint", "#FCE8E1"],
    ],
  },
  {
    group: "Status",
    tokens: [
      ["success", "bg-success", "#2A7353"],
      ["success-tint", "bg-success-tint", "#E4F1E9"],
      ["warning", "bg-warning", "#8A5A00"],
      ["warning-tint", "bg-warning-tint", "#F8EED9"],
      ["destructive", "bg-destructive", "#B42318"],
      ["destructive-tint", "bg-destructive-tint", "#FBE7E4"],
    ],
  },
  {
    group: "Charts (in order)",
    tokens: [
      ["chart-1 blue", "bg-chart-1", "#1D3461"],
      ["chart-2 coral", "bg-chart-2", "#E8664A"],
      ["chart-3 soft blue", "bg-chart-3", "#6B8CB8"],
      ["chart-4 ochre", "bg-chart-4", "#D9A441"],
      ["chart-5 sage", "bg-chart-5", "#5E8C7A"],
    ],
  },
];

const BUTTON_VARIANTS = [
  "default",
  "secondary",
  "outline",
  "ghost",
  "destructive",
  "link",
] as const;

const SOURCE = {
  n: 1,
  filename: "leave-policy.pdf",
  page: 1,
  snippet: "Every full-time employee receives 24 days of paid annual leave per calendar year.",
};

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-5">
      <div className="space-y-1">
        <p className="type-eyebrow text-muted-foreground">{eyebrow}</p>
        <h2 className="type-title">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function CitationChip({ source }: { source: typeof SOURCE }) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Source ${source.n}: ${source.filename}, page ${source.page}`}
          className="relative -top-1.5 mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-tint px-1 font-sans text-[0.6875rem] leading-none font-semibold text-primary transition-colors duration-150 hover:bg-primary hover:text-primary-foreground"
        >
          {source.n}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 gap-2 p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <FileText className="size-4 text-muted-foreground" aria-hidden />
          {source.filename}
          <span className="font-normal text-muted-foreground">· page {source.page}</span>
        </div>
        <p className="type-small text-muted-foreground">“{source.snippet}”</p>
        <Button variant="link" size="sm" className="h-auto justify-start px-0">
          Open document <ExternalLink />
        </Button>
      </PopoverContent>
    </Popover>
  );
}

export default function StyleguidePage() {
  if (process.env.NODE_ENV === "production") notFound();

  return (
    <main className="mx-auto w-full max-w-[1200px] space-y-14 px-4 py-10 md:px-8">
      <header className="space-y-4">
        <Wordmark />
        <div className="space-y-2">
          <p className="type-eyebrow text-coral-text">Design system</p>
          <h1 className="type-display">Warm ivory, editorial blue, a touch of coral</h1>
          <p className="max-w-2xl text-muted-foreground">
            Blue does the work; coral is the signature, used for small non-text accents only. Depth
            comes from thin rules, not shadows. Dev-only page.
          </p>
        </div>
      </header>

      <Separator />

      <Section eyebrow="Tokens" title="Colour">
        <div className="space-y-8">
          {COLORS.map(({ group, tokens }) => (
            <div key={group} className="space-y-3">
              <h3 className="text-sm font-semibold">{group}</h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {tokens.map(([name, className, hex]) => (
                  <div key={name} className="overflow-hidden rounded-lg border bg-card">
                    <div className={`h-16 border-b ${className}`} />
                    <div className="space-y-0.5 p-2.5">
                      <p className="text-sm font-medium">{name}</p>
                      <p className="font-mono text-xs text-muted-foreground">{hex}</p>
                      <p className="font-mono text-xs text-muted-foreground">{className}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Tokens" title="Typography">
        <div className="divide-y rounded-lg border bg-card">
          {[
            ["type-display · Newsreader 32/40", "type-display", "Quarterly knowledge review"],
            ["type-title · Newsreader 22/28", "type-title", "Action items from the planning sync"],
            [
              "type-answer · Newsreader 17/28 (assistant messages)",
              "type-answer",
              "Employees receive 24 days of paid annual leave per year, and up to five unused days can be carried over.",
            ],
            [
              "type-body · Inter 15/24 (default)",
              "type-body",
              "Upload documents to build your knowledge base.",
            ],
            [
              "type-small · Inter 13/20",
              "type-small text-muted-foreground",
              "Uploaded 3 minutes ago by Ana",
            ],
            [
              "type-eyebrow · Inter 12 uppercase",
              "type-eyebrow text-muted-foreground",
              "Meeting summary",
            ],
            [
              "font-mono · JetBrains Mono 13",
              "font-mono text-[0.8125rem]",
              "doc_7c52e743-9261-45f9",
            ],
          ].map(([label, className, sample]) => (
            <div key={label} className="grid gap-1 p-4 md:grid-cols-[260px_1fr] md:gap-6">
              <p className="type-small text-muted-foreground">{label}</p>
              <p className={className}>{sample}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Components" title="Buttons">
        <div className="space-y-4 rounded-lg border bg-card p-5">
          <div className="flex flex-wrap items-center gap-3">
            {BUTTON_VARIANTS.map((variant) => (
              <Button key={variant} variant={variant}>
                {variant}
              </Button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm">Small</Button>
            <Button>Default</Button>
            <Button size="lg">Large</Button>
            <Button>
              <Plus /> New chat
            </Button>
            <Button variant="outline">
              <Download /> Download PDF
            </Button>
            <Button disabled>
              <Loader2 className="animate-spin" /> Saving…
            </Button>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Delete document">
                  <Trash2 />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Delete document</TooltipContent>
            </Tooltip>
          </div>
        </div>
      </Section>

      <Section eyebrow="Components" title="Inputs">
        <div className="grid gap-6 rounded-lg border bg-card p-5 md:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="sg-email">Email</FieldLabel>
            <Input id="sg-email" type="email" placeholder="you@company.com" />
            <FieldDescription>We never share it.</FieldDescription>
          </Field>
          <Field data-invalid>
            <FieldLabel htmlFor="sg-password">Password</FieldLabel>
            <Input id="sg-password" type="password" defaultValue="short" aria-invalid />
            <FieldError>Use at least 8 characters.</FieldError>
          </Field>
          <Field>
            <FieldLabel htmlFor="sg-visibility">Visibility</FieldLabel>
            <Select defaultValue="employee">
              <SelectTrigger id="sg-visibility" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="employee">Everyone</SelectItem>
                <SelectItem value="manager">Managers & admins</SelectItem>
                <SelectItem value="admin">Admins only</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field orientation="horizontal">
            <Checkbox id="sg-remember" defaultChecked />
            <FieldLabel htmlFor="sg-remember">Email the action items to the team</FieldLabel>
          </Field>
          <Field className="md:col-span-2">
            <FieldLabel htmlFor="sg-message">Message</FieldLabel>
            <Textarea id="sg-message" placeholder="Ask about your documents…" />
          </Field>
        </div>
      </Section>

      <Section eyebrow="Components" title="Badges">
        <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-card p-5">
          <Badge variant="warning">
            <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-warning" />
            Processing
          </Badge>
          <Badge variant="success">
            <CheckCircle2 aria-hidden /> Ready
          </Badge>
          <Badge variant="destructive">
            <XCircle aria-hidden /> Failed
          </Badge>
          <Badge variant="info">Manager</Badge>
          <Badge variant="secondary">Employee</Badge>
          <Badge variant="outline">PDF</Badge>
          <Badge variant="coral">New</Badge>
          <Badge>Admin</Badge>
        </div>
      </Section>

      <Section eyebrow="Patterns" title="Card, citation and result card">
        <div className="grid items-start gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Leave policy 2026</CardTitle>
              <CardDescription>PDF · 1 page · uploaded by Ana</CardDescription>
              <CardAction>
                <Badge variant="success">
                  <CheckCircle2 aria-hidden /> Ready
                </Badge>
              </CardAction>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="type-answer">
                Employees receive <strong>24 days</strong> of paid annual leave
                <CitationChip source={SOURCE} />, and up to five unused days can be carried over to
                the next year
                <CitationChip source={SOURCE} />
                <span
                  aria-hidden
                  className="ml-0.5 inline-block h-[1.1em] w-0.5 translate-y-[0.2em] animate-pulse bg-coral"
                />
              </p>
              <div className="flex items-center gap-2 type-small text-muted-foreground">
                <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-coral" />
                <span>Planning…</span>
                <span aria-hidden>→</span>
                <span className="font-medium text-primary">Research agent</span>
              </div>
              <div className="space-y-1 border-t pt-3">
                <p className="type-eyebrow text-muted-foreground">Sources</p>
                <p className="type-small text-muted-foreground">
                  <span className="font-semibold text-primary">[1]</span> {SOURCE.filename}, page{" "}
                  {SOURCE.page}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <p className="type-eyebrow text-muted-foreground">Meeting summary</p>
              <CardTitle className="type-title">Q3 planning sync</CardTitle>
              <CardDescription>3 decisions · 4 action items</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <p>
                The team agreed to ship the reporting module before the October release and to move
                the analytics review to next sprint.
              </p>
              <ul className="space-y-1.5 type-small">
                <li>
                  <span className="font-medium">Rohit</span> · Draft the release notes · Friday
                </li>
                <li>
                  <span className="text-muted-foreground italic">Unassigned</span> · Book the
                  customer demo
                </li>
              </ul>
              <div className="space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            </CardContent>
            <CardFooter className="gap-2 border-t bg-muted/50 py-3">
              <Button variant="ghost" size="sm">
                <Copy /> Copy
              </Button>
              <Button variant="ghost" size="sm">
                <Download /> Download PDF
              </Button>
              <Button variant="ghost" size="sm">
                <ExternalLink /> Open in History
              </Button>
            </CardFooter>
          </Card>
        </div>
      </Section>

      <Section eyebrow="Patterns" title="Navigation item">
        <nav aria-label="Example navigation" className="w-64 space-y-1 rounded-lg bg-sidebar p-2">
          <a
            href="#"
            aria-current="page"
            className="relative flex items-center rounded-md bg-blue-tint px-3 py-2 text-sm font-medium text-primary before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-coral"
          >
            Chat
          </a>
          <a
            href="#"
            className="flex items-center rounded-md px-3 py-2 text-sm text-foreground transition-colors duration-150 hover:bg-accent hover:text-accent-foreground"
          >
            Documents
          </a>
        </nav>
      </Section>
    </main>
  );
}
