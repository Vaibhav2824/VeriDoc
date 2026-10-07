"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Check, Inbox, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfidenceChip, REASON_LABEL } from "@/components/veridoc/confidence";
import { formatValue, prettyName } from "@/components/veridoc/field-list";
import { getQueue, resolveQueueItem, type QueueItem } from "@/lib/api";

const keyOf = (q: QueueItem) => `${q.job_id}:${q.field_name}`;

function QueueRow({ item, onResolved }: { item: QueueItem; onResolved: (value: string) => void }) {
  const [value, setValue] = useState(
    item.extracted_value === null || item.extracted_value === undefined ? "" : String(item.extracted_value),
  );
  const [saving, setSaving] = useState(false);
  const inputId = `fix-${keyOf(item)}`;

  async function resolve() {
    setSaving(true);
    try {
      await resolveQueueItem(item.job_id, item.field_name, value === "" ? null : value);
      onResolved(value);
      toast.success(`${prettyName(item.field_name)} resolved`);
    } catch (err) {
      toast.error("Could not save", { description: err instanceof Error ? err.message : undefined });
    } finally {
      setSaving(false);
    }
  }

  return (
    <li className="grid gap-4 px-5 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] md:items-end">
      <div className="min-w-0">
        <Link
          href={`/jobs/?id=${encodeURIComponent(item.job_id)}`}
          className="block truncate text-xs text-muted-foreground hover:text-foreground hover:underline"
        >
          {item.doc_name}
        </Link>
        <div className="mt-1 flex items-center gap-2">
          <span className="font-medium capitalize">{prettyName(item.field_name)}</span>
          <ConfidenceChip confidence={item.confidence} status="abstained" />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{REASON_LABEL[item.reason] ?? item.reason}</p>
      </div>
      {item.resolved ? (
        <p className="flex items-center gap-2 text-sm text-success">
          <Check className="size-4" /> Resolved as{" "}
          <span className="font-medium text-foreground">{formatValue(item.corrected_value)}</span>
        </p>
      ) : (
        <div className="flex items-end gap-2">
          <div className="grid flex-1 gap-1.5">
            <label htmlFor={inputId} className="text-xs text-muted-foreground">
              Correct value (model read: {formatValue(item.extracted_value)})
            </label>
            <Input
              id={inputId}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && resolve()}
            />
          </div>
          <Button onClick={resolve} disabled={saving} className="active:scale-[0.98]">
            {saving ? "Saving" : "Confirm"}
          </Button>
        </div>
      )}
    </li>
  );
}

export default function QueuePage() {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"open" | "resolved">("open");

  const load = useCallback(() => {
    getQueue()
      .then((q) => {
        setError(null);
        setItems(q);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  useEffect(load, [load]);

  const markResolved = (key: string, value: string) =>
    setItems((prev) =>
      prev?.map((q) => (keyOf(q) === key ? { ...q, resolved: true, corrected_value: value || null } : q)) ?? null,
    );

  const shown = items?.filter((q) => (tab === "open" ? !q.resolved : q.resolved)) ?? [];
  const openCount = items?.filter((q) => !q.resolved).length ?? 0;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Review queue</h1>
          <p className="mt-2 max-w-[60ch] text-muted-foreground">
            Fields the gate withheld because confidence fell below 0.80. Confirm or correct each one.
          </p>
        </div>
        <Button variant="outline" onClick={load}>
          <RotateCw /> Refresh
        </Button>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as "open" | "resolved")} className="mt-8">
        <TabsList>
          <TabsTrigger value="open">Open ({openCount})</TabsTrigger>
          <TabsTrigger value="resolved">Resolved ({(items?.length ?? 0) - openCount})</TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="mt-4">
        {error ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
            {error === "Failed to fetch"
              ? "The API is unreachable. The free instance may be waking up; refresh in a minute."
              : error}
          </div>
        ) : items === null ? (
          <div className="space-y-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : shown.length === 0 ? (
          <div className="rounded-xl border border-dashed p-12 text-center">
            <Inbox className="mx-auto size-8 text-muted-foreground" strokeWidth={1.5} />
            <p className="mt-3 font-medium">{tab === "open" ? "Queue is clear" : "Nothing resolved yet"}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Low-confidence fields from new extractions will show up here.
            </p>
          </div>
        ) : (
          <ul className="divide-y rounded-xl border bg-card">
            {shown.map((q) => (
              <QueueRow key={keyOf(q)} item={q} onResolved={(v) => markResolved(keyOf(q), v)} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
