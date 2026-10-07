"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, FileWarning } from "lucide-react";
import AITaskList, { type AITask, type AITaskStatus } from "@/components/smoothui/ai-task-list";
import { ShimmeringText } from "@/components/unlumen-ui/shimmering-text";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfidenceChip, levelOf, REASON_LABEL } from "@/components/veridoc/confidence";
import { DocViewer } from "@/components/veridoc/doc-viewer";
import { FieldList, formatValue, prettyName } from "@/components/veridoc/field-list";
import { fieldsOf, getJob, plainFieldsOf, tablesOf, type Job } from "@/lib/api";
import { DEMO_ID, DEMO_IMAGE, loadDemoJob } from "@/lib/demo";
import { getPreview } from "@/lib/preview";
import { cn } from "@/lib/utils";

const POLL_MS = 2000;

function useJob(id: string | null) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const j = id === DEMO_ID ? await loadDemoJob() : await getJob(id!);
        if (cancelled) return;
        setJob(j);
        if (j.status === "pending" || j.status === "running") timer = setTimeout(poll, POLL_MS);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load job");
      }
    }
    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [id]);

  return { job, error };
}

/** The API only reports pending/running/done/failed, so sub-steps are shown as one running block. */
function pipelineTasks(status: Job["status"]): AITask[] {
  const stage = (doneWhen: boolean): AITaskStatus =>
    status === "failed" ? "failed" : doneWhen ? "done" : status === "running" ? "running" : "pending";
  return [
    { id: "upload", label: "Document received", status: "done" },
    {
      id: "pipeline",
      label: "Route, extract, verify",
      status: stage(status === "done"),
      children: [
        { id: "route", label: "Classify document type", status: stage(status === "done") },
        { id: "extract", label: "Extract into schema", status: stage(status === "done") },
        { id: "verify", label: "Score confidence and locate sources", status: stage(status === "done") },
      ],
    },
    { id: "gate", label: "Apply abstention gate", status: stage(status === "done") },
  ];
}

function JobView() {
  const id = useSearchParams().get("id");
  const { job, error } = useJob(id);
  const [active, setActive] = useState<string | null>(null);

  if (!id) {
    return <Empty title="No job selected" body="Upload a document or open the sample to see results here." />;
  }
  if (error) {
    return <Empty title="Could not load this job" body={error} />;
  }
  if (!job) {
    return (
      <div className="grid gap-6 md:grid-cols-2">
        <Skeleton className="aspect-[3/4] w-full" />
        <div className="space-y-3">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    );
  }

  const fields = fieldsOf(job.result);
  const pages = id === DEMO_ID ? [DEMO_IMAGE] : getPreview(id);
  const queue = job.review_queue ?? [];
  const abstained = fields.filter(([, f]) => levelOf(f.confidence, f.status) === "abstained").length;
  const plain = plainFieldsOf(job.result);
  const tables = tablesOf(job.result);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="min-w-0 truncate text-2xl font-semibold tracking-tight">{job.doc_name}</h1>
        {job.doc_type && (
          <Badge variant="secondary" className="capitalize">
            {prettyName(job.doc_type)}
          </Badge>
        )}
        {typeof job.result?.router_confidence === "number" && (
          <span className="text-sm text-muted-foreground">
            router {Math.round(job.result.router_confidence * 100)}% sure
          </span>
        )}
        {id === DEMO_ID && <Badge variant="outline">Sample run</Badge>}
      </div>

      {(job.status === "pending" || job.status === "running") && (
        <div className="max-w-md space-y-4 rounded-xl border bg-card p-6">
          <ShimmeringText text="Reading the document" className="text-lg font-medium" />
          <AITaskList tasks={pipelineTasks(job.status)} label="Pipeline" />
          <p className="text-xs text-muted-foreground">Usually 10 to 30 seconds on the free tier.</p>
        </div>
      )}

      {job.status === "failed" && (
        <div className="space-y-4 rounded-xl border border-destructive/30 bg-destructive/5 p-6">
          <AITaskList tasks={pipelineTasks("failed")} label="Pipeline" />
          <p className="text-sm text-destructive">{job.error ?? "Extraction failed."}</p>
        </div>
      )}

      {job.status === "done" && (
        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
          <div className="lg:sticky lg:top-24">
            {pages ? (
              <DocViewer pages={pages} fields={fields} active={active} onActive={setActive} />
            ) : (
              <div className="grid aspect-[3/4] place-items-center rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                The preview is only kept in the tab that uploaded the file, so it is not shown here.
              </div>
            )}
          </div>

          <Tabs defaultValue="fields">
            <TabsList>
              <TabsTrigger value="fields">Fields ({fields.length + plain.length})</TabsTrigger>
              <TabsTrigger value="review">Needs review ({queue.filter((q) => !q.resolved).length})</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
            </TabsList>

            <TabsContent value="fields" className="mt-4 space-y-6">
              <p className="text-sm text-muted-foreground">
                {fields.length > 0
                  ? `${fields.length - abstained} of ${fields.length} fields accepted. ${abstained > 0 ? `${abstained} withheld for review. ` : ""}Hover a field to find it on the page.`
                  : "Bank statements are extracted and PII-masked, but per-field verification currently covers invoices only."}
              </p>
              <FieldList fields={fields} plain={plain} active={active} onActive={setActive} />
              {tables.map(([name, rows]) => (
                <div key={name}>
                  <h2 className="mb-2 text-sm font-medium capitalize">
                    {prettyName(name)} <span className="font-normal text-muted-foreground">({rows.length})</span>
                  </h2>
                  <div className="max-h-[28rem] overflow-auto rounded-lg border">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-muted text-left text-xs text-muted-foreground">
                        <tr>
                          {Object.keys(rows[0]).map((k) => (
                            <th key={k} className="whitespace-nowrap px-3 py-2 font-medium capitalize">
                              {prettyName(k)}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {rows.map((row, i) => (
                          <tr key={i}>
                            {Object.values(row).map((v, j) => (
                              <td
                                key={j}
                                className={cn("px-3 py-2 tabular-nums", String(v ?? "").length < 24 && "whitespace-nowrap")}
                              >
                                {v === null ? <span className="text-muted-foreground">-</span> : formatValue(v)}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </TabsContent>

            <TabsContent value="review" className="mt-4">
              {queue.length === 0 ? (
                <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                  Nothing withheld. Every field cleared the confidence threshold.
                </p>
              ) : (
                <ul className="divide-y rounded-lg border">
                  {queue.map((q) => (
                    <li key={q.field_name} className="flex items-center justify-between gap-4 px-4 py-3">
                      <span className="min-w-0">
                        <span className="block text-sm font-medium capitalize">{prettyName(q.field_name)}</span>
                        <span className="block text-xs text-muted-foreground">{REASON_LABEL[q.reason] ?? q.reason}</span>
                      </span>
                      <ConfidenceChip confidence={q.confidence} status="abstained" />
                    </li>
                  ))}
                </ul>
              )}
              {queue.length > 0 && (
                <Link href="/queue/" className="mt-3 inline-block text-sm text-primary underline-offset-4 hover:underline">
                  Resolve these in the review queue
                </Link>
              )}
            </TabsContent>

            <TabsContent value="json" className="mt-4">
              <pre className="max-h-[70vh] overflow-auto rounded-lg border bg-muted/40 p-4 font-mono text-xs leading-relaxed">
                {JSON.stringify(job.result, null, 2)}
              </pre>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="mx-auto max-w-md rounded-xl border border-dashed p-10 text-center">
      <FileWarning className="mx-auto size-8 text-muted-foreground" strokeWidth={1.5} />
      <h1 className="mt-4 font-semibold">{title}</h1>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      <Link href="/" className="mt-4 inline-block text-sm text-primary underline-offset-4 hover:underline">
        Go to upload
      </Link>
    </div>
  );
}

export default function JobPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" /> Upload another
      </Link>
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <JobView />
      </Suspense>
    </div>
  );
}
