/** 1536 → "1.5 KB". Binary units, like the backend's 25 MB (25 × 2²⁰ bytes) limit. */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1).replace(/\.0$/, "")} ${units[unit]}`;
}

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
});
const dateTimeFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** "22 Oct 2026" */
export function formatDate(value: string | Date): string {
  return dateFormat.format(new Date(value));
}

/** "22 Oct 2026, 14:05" (local time) — for tooltips next to relative times. */
export function formatDateTime(value: string | Date): string {
  return dateTimeFormat.format(new Date(value));
}

const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
const STEPS: [limit: number, unit: Intl.RelativeTimeFormatUnit, seconds: number][] = [
  [60, "second", 1],
  [3600, "minute", 60],
  [86400, "hour", 3600],
  [604800, "day", 86400],
];

/** "just now", "5 minutes ago", "yesterday", "3 days ago"; a date after a week. */
export function formatRelative(value: string | Date, now: Date = new Date()): string {
  const date = new Date(value);
  const diff = (date.getTime() - now.getTime()) / 1000; // negative = past
  const abs = Math.abs(diff);
  if (abs < 45) return "just now";
  for (const [limit, unit, seconds] of STEPS) {
    if (abs < limit) return relative.format(Math.round(diff / seconds), unit);
  }
  return formatDate(date);
}
