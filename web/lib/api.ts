const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type JobStatus = "pending" | "running" | "done" | "failed";

export interface Job {
  job_id: string;
  doc_name: string;
  status: JobStatus;
  doc_type?: string;
  result?: Record<string, unknown>;
  review_queue?: QueueItem[];
  error?: string;
  created_at?: string;
}

export interface QueueItem {
  job_id: string;
  doc_name: string;
  field_name: string;
  extracted_value: unknown;
  confidence: number;
  reason: string;
  resolved?: boolean;
  corrected_value?: unknown;
}

export async function uploadDocument(file: File): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/v1/extract`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${BASE}/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getQueue(): Promise<QueueItem[]> {
  const res = await fetch(`${BASE}/v1/queue`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface Stats {
  total_jobs: number;
  by_status: Record<string, number>;
  by_doc_type: Record<string, number>;
  avg_processing_time_s: number | null;
  p95_processing_time_s: number | null;
  pending_review_items: number;
}

export async function getStats(): Promise<Stats> {
  const res = await fetch(`${BASE}/v1/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function resolveQueueItem(
  jobId: string,
  fieldName: string,
  correctedValue: unknown,
): Promise<void> {
  await fetch(`${BASE}/v1/queue/${jobId}/${fieldName}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ corrected_value: correctedValue, resolved_by: "human" }),
  });
}
