"use client";

import type { ExtractionField } from "@/lib/api";
import { LEVEL_STYLES, levelOf } from "@/components/veridoc/confidence";
import { cn } from "@/lib/utils";

interface Props {
  pages: string[];
  fields: [string, ExtractionField][];
  active: string | null;
  onActive: (name: string | null) => void;
}

/** Page images with each field's source bbox drawn on top. */
export function DocViewer({ pages, fields, active, onActive }: Props) {
  return (
    <div className="space-y-4">
      {pages.map((src, pageIdx) => (
        <div key={pageIdx} className="relative overflow-hidden rounded-lg border bg-white shadow-sm">
          {/* eslint-disable-next-line @next/next/no-img-element -- blob/data URLs */}
          <img src={src} alt={`Page ${pageIdx + 1} of the document`} className="block w-full" />
          {fields.map(([name, f]) => {
            const loc = f.source_location;
            if (!loc || loc.page !== pageIdx) return null;
            const [x0, y0, x1, y1] = loc.bbox;
            const isActive = active === name;
            return (
              <button
                key={name}
                type="button"
                aria-label={`${name.replace(/_/g, " ")}: ${String(f.value)}`}
                onMouseEnter={() => onActive(name)}
                onMouseLeave={() => onActive(null)}
                onFocus={() => onActive(name)}
                onBlur={() => onActive(null)}
                className={cn(
                  "absolute rounded-[3px] border-2 transition-[opacity,box-shadow] duration-200",
                  LEVEL_STYLES[levelOf(f.confidence, f.status)].box,
                  active && !isActive && "opacity-30",
                  isActive && "ring-4 ring-primary/30",
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
      ))}
    </div>
  );
}
