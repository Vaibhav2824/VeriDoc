"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getStats, type Stats } from "@/lib/api";

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="bg-white border rounded-xl p-5">
      <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</p>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

function BreakdownBar({
  label,
  data,
  colorMap,
}: {
  label: string;
  data: Record<string, number>;
  colorMap: Record<string, string>;
}) {
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  if (total === 0) return null;
  return (
    <div className="bg-white border rounded-xl p-5 space-y-3">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <div className="flex rounded-full overflow-hidden h-3">
        {Object.entries(data).map(([k, v]) => (
          <div
            key={k}
            style={{ width: `${(v / total) * 100}%` }}
            className={colorMap[k] ?? "bg-gray-300"}
            title={`${k}: ${v}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        {Object.entries(data).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5 text-xs text-gray-600">
            <span className={`w-2.5 h-2.5 rounded-full ${colorMap[k] ?? "bg-gray-300"}`} />
            <span className="capitalize">{k.replace("_", " ")}</span>
            <span className="font-semibold text-gray-900">{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const STATUS_COLORS: Record<string, string> = {
  done: "bg-green-500",
  running: "bg-blue-400",
  pending: "bg-gray-300",
  failed: "bg-red-400",
};

const DOCTYPE_COLORS: Record<string, string> = {
  invoice: "bg-indigo-500",
  bank_statement: "bg-purple-400",
};

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshed, setRefreshed] = useState<Date | null>(null);

  async function refresh() {
    try {
      const s = await getStats();
      setStats(s);
      setRefreshed(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load stats");
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15_000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">
            Live extraction stats — refreshes every 15 s
          </p>
        </div>
        <div className="flex items-center gap-4">
          {refreshed && (
            <span className="text-xs text-gray-400">
              Updated {refreshed.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={refresh}
            className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          {error} — is the API running at{" "}
          <code className="text-xs">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</code>?
        </div>
      )}

      {stats && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Total docs" value={stats.total_jobs} />
            <StatCard
              label="Avg latency"
              value={stats.avg_processing_time_s !== null ? `${stats.avg_processing_time_s}s` : "—"}
              sub="per document"
            />
            <StatCard
              label="p95 latency"
              value={stats.p95_processing_time_s !== null ? `${stats.p95_processing_time_s}s` : "—"}
              sub="per document"
            />
            <StatCard
              label="Pending review"
              value={stats.pending_review_items}
              sub={
                stats.pending_review_items > 0
                  ? "fields need human review"
                  : "queue empty"
              }
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <BreakdownBar
              label="Jobs by status"
              data={stats.by_status}
              colorMap={STATUS_COLORS}
            />
            <BreakdownBar
              label="Jobs by doc type"
              data={stats.by_doc_type}
              colorMap={DOCTYPE_COLORS}
            />
          </div>

          {stats.pending_review_items > 0 && (
            <div className="bg-orange-50 border border-orange-200 rounded-xl px-5 py-4 flex items-center justify-between">
              <div>
                <p className="font-semibold text-orange-800">
                  {stats.pending_review_items} field
                  {stats.pending_review_items !== 1 ? "s" : ""} awaiting review
                </p>
                <p className="text-xs text-orange-600 mt-0.5">
                  Low-confidence fields the abstention gate routed to human review
                </p>
              </div>
              <Link
                href="/queue"
                className="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 shrink-0"
              >
                Go to Review Queue →
              </Link>
            </div>
          )}

          <div className="bg-gray-50 border rounded-xl px-5 py-4 text-sm text-gray-500 space-y-1">
            <p className="font-semibold text-gray-700 text-xs uppercase tracking-wide">
              Eval numbers (from eval/REPORT.md)
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-2">
              {[
                ["Router accuracy", "100.0%", "130/130 docs"],
                ["Field F1 (M2)", "98.3%", "gate-adjusted"],
                ["ECE", "0.0115", "lower is better"],
                ["Auto @ 99% prec.", "84.3%", "coverage"],
              ].map(([label, val, note]) => (
                <div key={label} className="bg-white border rounded-lg p-3">
                  <p className="text-xs text-gray-400">{label}</p>
                  <p className="text-lg font-bold text-gray-900">{val}</p>
                  <p className="text-xs text-gray-400">{note}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {!stats && !error && (
        <p className="text-gray-400 animate-pulse">Loading stats…</p>
      )}
    </div>
  );
}
