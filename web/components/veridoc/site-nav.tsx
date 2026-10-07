"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggleButton } from "@/components/ui/skiper-ui/skiper26";
import { ApiStatus } from "@/components/veridoc/api-status";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Extract", match: (p: string) => p === "/" || p.startsWith("/jobs") },
  { href: "/queue/", label: "Review", match: (p: string) => p.startsWith("/queue") },
  { href: "/dashboard/", label: "Dashboard", match: (p: string) => p.startsWith("/dashboard") },
];

export function SiteNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
      <nav className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="grid size-7 place-items-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
            V
          </span>
          <span className="hidden sm:inline">VeriDoc</span>
        </Link>
        <div className="flex items-center gap-1 text-sm">
          {LINKS.map((l) => {
            const active = l.match(pathname);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-md px-2.5 py-1.5 text-muted-foreground transition-colors hover:text-foreground sm:px-3",
                  active && "bg-muted text-foreground",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </div>
        <div className="ml-auto flex items-center gap-4">
          <ApiStatus className="hidden md:inline-flex" />
          <ThemeToggleButton className="size-8 bg-foreground" variant="circle" start="top-right" />
        </div>
      </nav>
    </header>
  );
}
