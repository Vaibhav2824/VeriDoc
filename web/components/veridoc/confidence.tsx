import { cn } from "@/lib/utils";

/** Mirrors the API default (CONFIDENCE_THRESHOLD=0.80). */
export const CONFIDENCE_THRESHOLD = 0.8;

export type Level = "high" | "review" | "abstained";

export function levelOf(confidence: number, status?: string): Level {
  if (status === "abstained" || confidence < CONFIDENCE_THRESHOLD) return "abstained";
  return confidence >= 0.9 ? "high" : "review";
}

export const LEVEL_STYLES: Record<Level, { chip: string; box: string; label: string }> = {
  high: {
    chip: "bg-success/12 text-success ring-success/25",
    box: "border-success bg-success/10",
    label: "Auto-accepted",
  },
  review: {
    chip: "bg-warning/15 text-warning ring-warning/30",
    box: "border-warning bg-warning/10",
    label: "Accepted, close to the threshold",
  },
  abstained: {
    chip: "bg-destructive/12 text-destructive ring-destructive/25",
    box: "border-destructive bg-destructive/10",
    label: "Abstained, sent to review",
  },
};

export function ConfidenceChip({
  confidence,
  status,
  className,
}: {
  confidence: number;
  status?: string;
  className?: string;
}) {
  const level = levelOf(confidence, status);
  return (
    <span
      title={LEVEL_STYLES[level].label}
      className={cn(
        "inline-flex h-6 min-w-12 items-center justify-center rounded-full px-2 font-mono text-xs font-medium tabular-nums ring-1 ring-inset",
        LEVEL_STYLES[level].chip,
        className,
      )}
    >
      {Math.round(confidence * 100)}%
    </span>
  );
}

export const REASON_LABEL: Record<string, string> = {
  abstained: "Abstained by the gate",
  low_confidence: "Confidence below 0.80",
  no_source_location: "No source location found on the page",
};
