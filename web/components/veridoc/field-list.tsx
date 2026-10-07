"use client";

import { MapPinOff } from "lucide-react";
import type { ExtractionField } from "@/lib/api";
import { ConfidenceChip, levelOf } from "@/components/veridoc/confidence";
import { cn } from "@/lib/utils";

export const prettyName = (k: string) => k.replace(/_/g, " ");

export function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === "") return "Not found";
  if (typeof v === "number") return v.toLocaleString("en-US"); // fixed locale: SSR and browser must match
  if (typeof v === "object") {
    return Object.entries(v)
      .filter(([, x]) => x !== null && x !== undefined)
      .map(([k, x]) => `${prettyName(k)}: ${formatValue(x)}`)
      .join(", ");
  }
  return String(v);
}

export function FieldList({
  fields,
  plain = [],
  active,
  onActive,
}: {
  fields: [string, ExtractionField][];
  plain?: [string, unknown][];
  active: string | null;
  onActive: (name: string | null) => void;
}) {
  return (
    <ul className="divide-y rounded-lg border bg-card">
      {plain.map(([name, v]) => (
        <li
          key={name}
          className="grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-3 px-4 py-2.5 sm:grid-cols-[minmax(0,10rem)_1fr_auto]"
        >
          <span className="truncate text-xs capitalize text-muted-foreground">{prettyName(name)}</span>
          <span className="min-w-0 break-words text-sm">{formatValue(v)}</span>
          <span className="text-xs text-muted-foreground">unverified</span>
        </li>
      ))}
      {fields.map(([name, f]) => {
        const abstained = levelOf(f.confidence, f.status) === "abstained";
        const missing = f.value === null || f.value === undefined;
        return (
          <li
            key={name}
            onMouseEnter={() => onActive(name)}
            onMouseLeave={() => onActive(null)}
            className={cn(
              "grid grid-cols-[minmax(0,8rem)_1fr_auto] items-center gap-3 px-4 py-2.5 transition-colors sm:grid-cols-[minmax(0,10rem)_1fr_auto]",
              active === name && "bg-accent/60",
            )}
          >
            <span className="truncate text-xs capitalize text-muted-foreground">{prettyName(name)}</span>
            <span
              className={cn(
                "min-w-0 whitespace-pre-line break-words text-sm",
                abstained && "text-destructive",
                missing && "italic text-muted-foreground",
              )}
            >
              {formatValue(f.value)}
            </span>
            <span className="flex items-center gap-2">
              {!f.source_location && !missing && (
                <MapPinOff className="size-4 text-warning" aria-label="No source location (ungrounded)" />
              )}
              <ConfidenceChip confidence={f.confidence} status={f.status} />
            </span>
          </li>
        );
      })}
    </ul>
  );
}
