"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

type State = "checking" | "online" | "offline";

const LABEL: Record<State, string> = {
  checking: "Waking API",
  online: "API online",
  offline: "API offline",
};

// The free Render instance sleeps when idle; the first request can take ~50 s.
export function ApiStatus({ className }: { className?: string }) {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then(() => !cancelled && setState("online"))
      .catch(() => !cancelled && setState("offline"));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <span
      className={cn("inline-flex items-center gap-2 text-xs text-muted-foreground", className)}
      role="status"
    >
      <span
        aria-hidden
        className={cn(
          "size-2 rounded-full",
          state === "online" && "bg-success",
          state === "offline" && "bg-destructive",
          state === "checking" && "animate-pulse bg-warning motion-reduce:animate-none",
        )}
      />
      {LABEL[state]}
    </span>
  );
}
