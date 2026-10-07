"use client";

import { motion, useReducedMotion } from "motion/react";
import { FileSearch, GitFork, ShieldCheck, UserCheck } from "lucide-react";

const STEPS = [
  {
    icon: GitFork,
    title: "Route",
    body: "A TF-IDF classifier trained on 130 labeled documents picks invoice or bank statement in under a millisecond, using zero tokens.",
  },
  {
    icon: FileSearch,
    title: "Extract",
    body: "Gemini Flash reads the page into a strict Pydantic schema. Invalid output is retried a bounded number of times, then abstained.",
  },
  {
    icon: ShieldCheck,
    title: "Verify",
    body: "A second pass checks every field against the page and returns a confidence plus the box it was read from.",
  },
  {
    icon: UserCheck,
    title: "Gate",
    body: "Fields under 0.80 confidence are withheld and queued for a person instead of being guessed.",
  },
];

export function PipelineSteps() {
  const reduce = useReducedMotion();
  return (
    <ol className="grid gap-8 md:grid-cols-4 md:gap-6">
      {STEPS.map((s, i) => (
        <motion.li
          key={s.title}
          initial={reduce ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="relative"
        >
          <div className="flex items-center gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent text-accent-foreground">
              <s.icon className="size-5" strokeWidth={1.75} />
            </span>
            {i < STEPS.length - 1 && <span aria-hidden className="hidden h-px flex-1 bg-border md:block" />}
          </div>
          <h3 className="mt-4 font-semibold">{s.title}</h3>
          <p className="mt-1.5 max-w-[34ch] text-sm leading-relaxed text-muted-foreground">{s.body}</p>
        </motion.li>
      ))}
    </ol>
  );
}
