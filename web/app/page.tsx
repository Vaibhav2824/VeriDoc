import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { CountUp } from "@/components/unlumen-ui/count-up";
import { buttonVariants } from "@/components/ui/button";
import { HeroScan } from "@/components/veridoc/hero-scan";
import { PipelineSteps } from "@/components/veridoc/pipeline-steps";
import { UploadPanel } from "@/components/veridoc/upload-panel";
import { DEMO_ID } from "@/lib/demo";
import { cn } from "@/lib/utils";

const REPORT_URL = "https://github.com/Vaibhav2824/VeriDoc/blob/main/eval/REPORT.md";

// Numbers from eval/REPORT.md (M2 trust metrics, M3 router).
const METRICS = [
  { value: 84.3, suffix: "%", label: "of fields auto-processed at 99% precision" },
  { value: 0.0115, suffix: "", label: "expected calibration error" },
  { value: 0, suffix: "%", label: "hallucination rate (value with no source location)" },
];

export default function Home() {
  return (
    <>
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 pb-20 pt-12 sm:px-6 md:grid-cols-[5fr_6fr] md:pt-20 lg:gap-20">
        <div>
          <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight md:text-5xl lg:text-6xl">
            Document extraction that shows its work.
          </h1>
          <p className="mt-6 max-w-[42ch] text-lg leading-relaxed text-muted-foreground">
            Every field carries a calibrated confidence and the exact spot it came from. Unsure fields
            go to a human.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href="#extract" className={cn(buttonVariants({ size: "lg" }), "active:scale-[0.98]")}>
              Extract a document <ArrowRight />
            </a>
            <Link
              href={`/jobs/?id=${DEMO_ID}`}
              className={cn(buttonVariants({ size: "lg", variant: "outline" }), "active:scale-[0.98]")}
            >
              Open the sample
            </Link>
          </div>
        </div>
        <HeroScan />
      </section>

      <section id="extract" className="scroll-mt-20 border-y bg-muted/40">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 md:grid-cols-[2fr_3fr] md:py-24">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">Try it on your own document</h2>
            <p className="mt-3 max-w-[40ch] leading-relaxed text-muted-foreground">
              Invoices and bank statements are detected automatically. Results stream back with a
              confidence for every field.
            </p>
          </div>
          <UploadPanel />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 md:py-28">
        <h2 className="text-balance text-3xl font-semibold tracking-tight">
          Four steps, each one allowed to say no
        </h2>
        <div className="mt-12">
          <PipelineSteps />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
        <div className="grid gap-4 md:grid-cols-3 md:grid-rows-3">
          <div className="flex flex-col justify-between rounded-2xl bg-primary p-8 text-primary-foreground md:col-span-2 md:row-span-3 md:p-10">
            <h2 className="max-w-[20ch] text-2xl font-semibold tracking-tight md:text-3xl">
              Measured on a labeled benchmark, not claimed
            </h2>
            <div className="mt-12">
              <div className="text-6xl font-semibold tracking-tighter tabular-nums md:text-8xl">
                <CountUp to={98.3} duration={1.4} />%
              </div>
              <p className="mt-2 text-primary-foreground/80">macro field accuracy after the abstention gate</p>
            </div>
          </div>
          {METRICS.map((m) => (
            <div key={m.label} className="rounded-2xl border bg-card p-6">
              <div className="text-4xl font-semibold tracking-tight tabular-nums">
                <CountUp to={m.value} duration={1.2} />
                {m.suffix}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{m.label}</p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-sm text-muted-foreground">
          Trust metrics on 29 labeled documents, routing on 130.{" "}
          <a href={REPORT_URL} target="_blank" rel="noreferrer" className="underline underline-offset-4 hover:text-foreground">
            Read the eval report
          </a>
        </p>
      </section>
    </>
  );
}
