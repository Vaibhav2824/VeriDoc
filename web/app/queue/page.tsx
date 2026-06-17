"use client";

import { useEffect, useState } from "react";
import { getQueue, resolveQueueItem, type QueueItem } from "@/lib/api";
import Link from "next/link";

function QueueCard({ item, onResolved }: { item: QueueItem; onResolved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(item.extracted_value ?? ""));
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(item.resolved ?? false);

  async function handleResolve() {
    setSaving(true);
    await resolveQueueItem(item.job_id, item.field_name, value || item.extracted_value);
    setSaving(false);
    setDone(true);
    setEditing(false);
    onResolved();
  }

  const pct = Math.round(item.confidence * 100);

  return (
    <div className={`bg-white border rounded-xl p-5 space-y-3 ${done ? "opacity-50" : ""}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-gray-400 mb-0.5">
            <Link href={`/jobs/${item.job_id}`} className="hover:underline">
              {item.doc_name}
            </Link>
          </p>
          <p className="font-semibold text-gray-900 font-mono">{item.field_name}</p>
        </div>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium border shrink-0 ${
            pct >= 70
              ? "bg-yellow-100 text-yellow-800 border-yellow-200"
              : "bg-red-100 text-red-800 border-red-200"
          }`}
        >
          {pct}% confidence
        </span>
      </div>

      <p className="text-xs text-gray-500">{item.reason}</p>

      <div className="flex items-center gap-3">
        {done ? (
          <span className="text-green-600 text-sm font-medium">Resolved</span>
        ) : editing ? (
          <>
            <input
              className="border rounded-lg px-3 py-1.5 text-sm flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              autoFocus
            />
            <button
              onClick={handleResolve}
              disabled={saving}
              className="px-3 py-1.5 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Confirm"}
            </button>
            <button
              onClick={() => setEditing(false)}
              className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <span className="text-sm text-gray-700 flex-1">
              Extracted:{" "}
              <span className="font-medium">
                {item.extracted_value !== null && item.extracted_value !== undefined
                  ? String(item.extracted_value)
                  : <span className="italic text-gray-400">empty</span>}
              </span>
            </span>
            <button
              onClick={() => setEditing(true)}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
            >
              Review &amp; Approve
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default function QueuePage() {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const data = await getQueue();
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load queue");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  const pending = items.filter((i) => !i.resolved);
  const resolved = items.filter((i) => i.resolved);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Review Queue</h1>
          <p className="text-gray-500 text-sm mt-1">
            Fields the abstention gate flagged for human review
          </p>
        </div>
        {pending.length > 0 && (
          <span className="px-3 py-1 bg-orange-100 text-orange-800 rounded-full text-sm font-medium">
            {pending.length} pending
          </span>
        )}
      </div>

      {loading && <p className="text-gray-400 animate-pulse">Loading…</p>}
      {error && (
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {!loading && !error && pending.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">✓</p>
          <p className="font-medium">All caught up — nothing to review</p>
          <Link href="/" className="mt-4 inline-block text-sm text-blue-600 hover:underline">
            Upload a document
          </Link>
        </div>
      )}

      {pending.length > 0 && (
        <div className="space-y-4">
          {pending.map((item) => (
            <QueueCard key={`${item.job_id}-${item.field_name}`} item={item} onResolved={refresh} />
          ))}
        </div>
      )}

      {resolved.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">
            Resolved ({resolved.length})
          </h2>
          {resolved.map((item) => (
            <QueueCard key={`${item.job_id}-${item.field_name}`} item={item} onResolved={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}
