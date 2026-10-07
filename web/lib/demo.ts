import { CONFIDENCE_THRESHOLD as THRESHOLD } from "@/components/veridoc/confidence";
import { fieldsOf, type ExtractionResult, type Job, type QueueItem } from "@/lib/api";


export const DEMO_ID = "demo";
const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export const DEMO_IMAGE = `${BASE_PATH}/demo/invoice.png`;

/**
 * A real pipeline run (Gemini Flash) on benchmark invoice 51109301, shipped as
 * static JSON so the demo works even while the free-tier API is asleep.
 */
export async function loadDemoJob(): Promise<Job> {
  const res = await fetch(`${BASE_PATH}/demo/invoice.json`);
  if (!res.ok) throw new Error("Demo data missing");
  const result = (await res.json()) as ExtractionResult;
  return {
    job_id: DEMO_ID,
    doc_name: "invoice_51109301.pdf",
    status: "done",
    doc_type: result.doc_type,
    result,
    review_queue: demoQueue(result),
  };
}

/** Same rule as services/api/models/review_queue.build_review_queue. */
function demoQueue(result: ExtractionResult): QueueItem[] {
  return fieldsOf(result).flatMap(([name, f]) => {
    const reason =
      f.status === "abstained"
        ? "abstained"
        : f.value !== null && !f.source_location
          ? "no_source_location"
          : f.confidence < THRESHOLD
            ? "low_confidence"
            : null;
    return reason
      ? [{ job_id: DEMO_ID, doc_name: "invoice_51109301.pdf", field_name: name, extracted_value: f.value, confidence: f.confidence, reason }]
      : [];
  });
}
