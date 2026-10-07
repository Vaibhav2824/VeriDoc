"use client";

import { useRef } from "react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import demo from "@/public/demo/invoice.json";
import { fieldsOf, type ExtractionField, type ExtractionResult } from "@/lib/api";
import { DEMO_IMAGE } from "@/lib/demo";
import { ConfidenceChip, LEVEL_STYLES, levelOf } from "@/components/veridoc/confidence";
import { formatValue, prettyName } from "@/components/veridoc/field-list";
import { cn } from "@/lib/utils";

gsap.registerPlugin(useGSAP);

/** Fraction of the page height shown (the invoice content sits in the top half). */
const CROP = 0.57;
const SCAN_SECONDS = 2.4;
const SHOWN = ["invoice_number", "vendor_name", "buyer_gstin", "total_amount", "due_date"];

const fields = fieldsOf(demo as ExtractionResult);
const rows = SHOWN.map((name) => fields.find(([n]) => n === name)).filter(
  (r): r is [string, ExtractionField] => Boolean(r),
);
/** When the scan line reaches a field (unlocated fields resolve at the end). */
const revealAt = (f: ExtractionField) =>
  (f.source_location ? Math.min(f.source_location.bbox[1] / CROP, 1) : 1) * SCAN_SECONDS;

/**
 * The hero tells the product story on a real extraction: a scan passes over
 * the page and each field lands with its box and confidence as it is read.
 */
export function HeroScan() {
  const scope = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const tl = gsap.timeline({ delay: 0.3 });
        tl.from(".hero-doc", { y: 24, opacity: 0, duration: 0.7, ease: "power3.out" });
        tl.addLabel("scan");
        tl.fromTo(
          ".scan-line",
          { top: "0%", opacity: 1 },
          { top: "100%", duration: SCAN_SECONDS, ease: "none" },
          "scan",
        );
        gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((el) => {
          tl.from(
            el,
            { opacity: 0, scale: el.dataset.kind === "box" ? 0.85 : 1, x: el.dataset.kind === "row" ? -10 : 0, duration: 0.35, ease: "back.out(2)" },
            `scan+=${el.dataset.reveal}`,
          );
        });
        tl.to(".scan-line", { opacity: 0, duration: 0.3 });
      });
      return () => mm.revert();
    },
    { scope },
  );

  return (
    <div ref={scope} className="relative">
      <div
        className="hero-doc relative overflow-hidden rounded-xl border bg-white shadow-[0_24px_60px_-24px_color-mix(in_oklch,var(--primary),transparent_70%)]"
        style={{ aspectRatio: `1241 / ${Math.round(1754 * CROP)}` }}
      >
        <div className="relative">
          {/* eslint-disable-next-line @next/next/no-img-element -- static export, unoptimized */}
          <img src={DEMO_IMAGE} alt="Sample invoice from the VeriDoc benchmark" className="block w-full" />
          {fields.map(([name, f]) => {
            if (!f.source_location) return null;
            const [x0, y0, x1, y1] = f.source_location.bbox;
            return (
              <span
                key={name}
                data-reveal={revealAt(f)}
                data-kind="box"
                className={cn(
                  "absolute rounded-[3px] border-2",
                  LEVEL_STYLES[levelOf(f.confidence, f.status)].box,
                )}
                style={{
                  left: `${x0 * 100}%`,
                  top: `${y0 * 100}%`,
                  width: `${(x1 - x0) * 100}%`,
                  height: `${(y1 - y0) * 100}%`,
                }}
              />
            );
          })}
        </div>
        <span
          aria-hidden
          className="scan-line pointer-events-none absolute inset-x-0 top-0 h-px bg-primary opacity-0 shadow-[0_0_24px_6px_color-mix(in_oklch,var(--primary),transparent_60%)]"
        />
      </div>

      <div className="relative mx-3 -mt-6 rounded-xl border bg-card/95 p-1.5 shadow-xl backdrop-blur md:absolute md:-bottom-10 md:-left-10 md:mx-0 md:mt-0 md:w-[22rem]">
        <ul className="divide-y">
          {rows.map(([name, f]) => (
            <li
              key={name}
              data-reveal={revealAt(f) + 0.1}
              data-kind="row"
              className="flex items-center justify-between gap-3 px-3 py-2"
            >
              <span className="min-w-0">
                <span className="block text-[11px] capitalize text-muted-foreground">{prettyName(name)}</span>
                <span className="block truncate text-sm font-medium">{formatValue(f.value)}</span>
              </span>
              <ConfidenceChip confidence={f.confidence} status={f.status} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
