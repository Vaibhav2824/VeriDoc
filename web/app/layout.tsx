import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Providers } from "@/components/providers";
import { SiteNav } from "@/components/veridoc/site-nav";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "VeriDoc | Document extraction you can audit",
  description:
    "VLM document extraction where every field carries a calibrated confidence and a source location, and low-confidence fields go to a human instead of being guessed.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="flex min-h-[100dvh] flex-col font-sans">
        <Providers>
          <SiteNav />
          <main className="flex-1">{children}</main>
          <footer className="border-t">
            <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-muted-foreground sm:px-6">
              <span>VeriDoc. Built on free tiers: GitHub Pages, Render, Supabase.</span>
              <a
                href="https://github.com/Vaibhav2824/VeriDoc"
                className="transition-colors hover:text-foreground"
                target="_blank"
                rel="noreferrer"
              >
                Source on GitHub
              </a>
            </div>
          </footer>
        </Providers>
      </body>
    </html>
  );
}
