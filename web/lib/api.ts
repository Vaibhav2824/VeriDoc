const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type JobStatus = "pending" | "running" | "done" | "failed";

export interface SourceLocation {
  page: number;
  /** [x0, y0, x1, y1], normalized 0-1 */
  bbox: [number, number, number, number];
}

export interface ExtractionField {
  value: unknown;
  confidence: number;
  source_location: SourceLocation | null;
  status: "extracted" | "abstained";
}

export interface ExtractionResult {
  doc_type: string;
  router_confidence?: number;
  invoice?: Record<string, unknown> | null;
  bank_statement?: Record<string, unknown> | null;
}

export interface Job {
  job_id: string;
  doc_name: string;
  status: JobStatus;
  doc_type?: string;
  result?: ExtractionResult | null;
  review_queue?: QueueItem[];
  error?: string | null;
  created_at?: string | null;
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

export interface Stats {
  total_jobs: number;
  by_status: Record<string, number>;
  by_doc_type: Record<string, number>;
  avg_processing_time_s: number | null;
  p95_processing_time_s: number | null;
  pending_review_items: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export function uploadDocument(file: File): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  return request("/v1/extract", { method: "POST", body: form });
}

export const getJob = (jobId: string) => request<Job>(`/v1/jobs/${encodeURIComponent(jobId)}`);
export const getQueue = () => request<QueueItem[]>("/v1/queue");
export const getStats = () => request<Stats>("/v1/stats");
export const getHealth = () => request<{ status: string; db: string }>("/health");

export function resolveQueueItem(jobId: string, fieldName: string, correctedValue: unknown) {
  return request<{ status: string }>(
    `/v1/queue/${encodeURIComponent(jobId)}/${encodeURIComponent(fieldName)}/resolve`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corrected_value: correctedValue, resolved_by: "human" }),
    },
  );
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);
const isField = (v: unknown): v is ExtractionField => isObject(v) && "confidence" in v;

const payloadOf = (r: ExtractionResult | null | undefined) =>
  Object.entries(r?.invoice ?? r?.bank_statement ?? {});

/** Verified fields (value + confidence + source). */
export const fieldsOf = (r: ExtractionResult | null | undefined) =>
  payloadOf(r).filter((e): e is [string, ExtractionField] => isField(e[1]));

/** Values extracted without verification (bank statements have no verifier yet). */
export const plainFieldsOf = (r: ExtractionResult | null | undefined) =>
  payloadOf(r).filter(([, v]) => !isField(v) && !Array.isArray(v));

/** Repeating rows such as invoice line items or statement transactions. */
export const tablesOf = (r: ExtractionResult | null | undefined) =>
  payloadOf(r).filter((e): e is [string, Record<string, unknown>[]] => Array.isArray(e[1]) && isObject(e[1][0]));

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_TYPES = ".pdf,.png,.jpg,.jpeg";
