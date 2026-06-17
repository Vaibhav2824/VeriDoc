"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { getJob, type Job } from "@/lib/api";

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 90 ? "bg-green-100 text-green-800 border-green-200"
    : pct >= 70 ? "bg-yellow-100 text-yellow-800 border-yellow-200"
    : "bg-red-100 text-red-800 border-red-200";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${color}`}>
      {pct}%
    </span>
  );
}

function FieldRow({ name, field }: { name: string; field: Record<string, unknown> }) {
  const value = field.value;
  const confidence = typeof field.confidence === "number" ? field.confidence : 0;
  const status = field.status as string;
  const abstained = status === "abstained";

  return (
    <tr className={`border-b last:border-0 ${abstained ? "bg-red-50" : ""}`}>
      <td className="py-2 pr-4 font-mono text-xs text-gray-500 w-40">{name}</td>
      <td className="py-2 pr-4 text-sm">
        {abstained ? (
          <span className="text-red-500 italic">abstained — needs review</span>
        ) : value === null || value === undefined ? (
          <span className="text-gray-400">—</span>
        ) : (
          <span className="font-medium">{String(value)}</span>
        )}
      </td>
      <td className="py-2">
        <ConfidenceBadge value={confidence} />
      </td>
    </tr>
  );
}

function ExtractionResult({ job }: { job: Job }) {
  const result = job.result as Record<string, unknown> | undefined;
  if (!result) return null;

  const docType = job.doc_type ?? result.doc_type;
  const routerConf = typeof result.router_confidence === "number"
    ? Math.round((result.router_confidence as number) * 100)
    : null;

  const payload = (result.invoice ?? result.bank_statement) as Record<string, unknown> | undefined;
  if (!payload) return <p className="text-gray-500">No extraction data.</p>;

  // Separate ExtractionField objects from nested objects/arrays
  const fieldEntries = Object.entries(payload).filter(
    ([, v]) => v !== null && typeof v === "object" && !Array.isArray(v) &&
               "confidence" in (v as object)
  ) as [string, Record<string, unknown>][];

  const queue = job.review_queue ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <span className="px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-sm font-medium capitalize">
          {String(docType).replace("_", " ")}
        </span>
        {routerConf !== null && (
          <span className="text-xs text-gray-500">Router confidence: {routerConf}%</span>
        )}
        {queue.length > 0 && (
          <Link
            href="/queue"
            className="ml-auto text-xs text-orange-600 hover:underline font-medium"
          >
            {queue.length} field{queue.length !== 1 ? "s" : ""} need review →
          </Link>
        )}
      </div>

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-gray-50 border-b text-xs text-gray-500 uppercase tracking-wider">
              <th className="py-2 px-4">Field</th>
              <th className="py-2 px-4">Value</th>
              <th className="py-2 px-4">Confidence</th>
            </tr>
          </thead>
          <tbody className="px-4">
            {fieldEntries.map(([name, field]) => (
              <FieldRow key={name} name={name} field={field} />
            ))}
          </tbody>
        </table>
      </div>

      {queue.length > 0 && (
        <div className="border border-orange-200 bg-orange-50 rounded-xl p-4">
          <p className="font-semibold text-orange-800 text-sm mb-2">
            Fields routed to human review
          </p>
          <ul className="space-y-1">
            {queue.map((item) => (
              <li key={item.field_name} className="text-xs text-orange-700 font-mono">
                {item.field_name} — {item.reason} (confidence {Math.round(item.confidence * 100)}%)
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const j = await getJob(id);
        if (!cancelled) {
          setJob(j);
          if (j.status === "pending" || j.status === "running") {
            setTimeout(poll, 2000);
          }
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to fetch job");
      }
    }

    poll();
    return () => { cancelled = true; };
  }, [id]);

  if (error) {
    return (
      <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
        {error}
      </div>
    );
  }

  if (!job) {
    return <p className="text-gray-400 animate-pulse">Loading…</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-sm text-gray-500 hover:text-gray-900">← Upload another</Link>
        <h1 className="text-xl font-semibold truncate">{job.doc_name}</h1>
        <StatusBadge status={job.status} />
      </div>

      {(job.status === "pending" || job.status === "running") && (
        <div className="flex items-center gap-3 text-blue-600 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
          <span className="inline-block w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          Extracting document… this takes 10–30 seconds
        </div>
      )}

      {job.status === "done" && <ExtractionResult job={job} />}

      {job.status === "failed" && (
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
          <p className="font-semibold">Extraction failed</p>
          <p className="text-sm mt-1">{job.error}</p>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "bg-gray-100 text-gray-600",
    running: "bg-blue-100 text-blue-700",
    done: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${map[status] ?? ""}`}>
      {status}
    </span>
  );
}
