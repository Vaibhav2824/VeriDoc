"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { CountUp } from "@/components/unlumen-ui/count-up";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { Skeleton } from "@/components/ui/skeleton";
import { prettyName } from "@/components/veridoc/field-list";
import { getStats, type Stats } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  done: "var(--chart-2)",
  running: "var(--chart-1)",
  pending: "var(--chart-5)",
  failed: "var(--chart-4)",
};

const chartConfig = { count: { label: "Jobs", color: "var(--chart-1)" } } satisfies ChartConfig;

function Kpi({ label, value, suffix = "" }: { label: string; value: number | null; suffix?: string }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums">
        {value === null ? <span className="text-muted-foreground">-</span> : <><CountUp to={value} duration={1} />{suffix}</>}
      </p>
    </div>
  );
}

function BreakdownChart({ title, data }: { title: string; data: { name: string; count: number; fill: string }[] }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <h2 className="text-sm font-medium">{title}</h2>
      {data.length === 0 ? (
        <p className="grid h-48 place-items-center text-sm text-muted-foreground">No jobs yet</p>
      ) : (
        <ChartContainer config={chartConfig} className="mt-4 h-48 w-full">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid horizontal={false} />
            <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="name" width={96} tickLine={false} axisLine={false} />
            <ChartTooltip cursor={false} content={<ChartTooltipContent hideLabel />} />
            <Bar dataKey="count" radius={4} />
          </BarChart>
        </ChartContainer>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getStats()
      .then(setStats)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  const done = stats?.by_status.done ?? 0;
  const failed = stats?.by_status.failed ?? 0;
  const successRate = done + failed > 0 ? Math.round((done / (done + failed)) * 1000) / 10 : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-2 text-muted-foreground">Live numbers from every document processed by this deployment.</p>

      {error ? (
        <div className="mt-8 rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
          {error === "Failed to fetch"
            ? "The API is unreachable. The free instance may be waking up; reload in a minute."
            : error}
        </div>
      ) : !stats ? (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi label="Documents processed" value={stats.total_jobs} />
            <Kpi label="p95 processing time" value={stats.p95_processing_time_s} suffix=" s" />
            <Kpi label="Fields awaiting review" value={stats.pending_review_items} />
            <Kpi label="Extraction success rate" value={successRate} suffix="%" />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <BreakdownChart
              title="Jobs by status"
              data={Object.entries(stats.by_status).map(([name, count]) => ({
                name,
                count,
                fill: STATUS_COLOR[name] ?? "var(--chart-5)",
              }))}
            />
            <BreakdownChart
              title="Jobs by document type"
              data={Object.entries(stats.by_doc_type).map(([name, count], i) => ({
                name: prettyName(name),
                count,
                fill: `var(--chart-${(i % 2) + 1})`,
              }))}
            />
          </div>
        </>
      )}
    </div>
  );
}
