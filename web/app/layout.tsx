import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "VeriDoc — Trusted Document Intelligence",
  description: "VLM-native extraction with calibrated confidence and abstention.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-gray-50 text-gray-900">
        <nav className="border-b bg-white px-6 py-3 flex items-center gap-6 text-sm shadow-sm">
          <Link href="/" className="font-bold text-base tracking-tight text-gray-900">
            VeriDoc
          </Link>
          <Link href="/" className="text-gray-500 hover:text-gray-900 transition-colors">
            Extract
          </Link>
          <Link href="/queue" className="text-gray-500 hover:text-gray-900 transition-colors">
            Review Queue
          </Link>
          <Link href="/dashboard" className="text-gray-500 hover:text-gray-900 transition-colors">
            Dashboard
          </Link>
        </nav>
        <main className="flex-1 mx-auto w-full max-w-5xl px-6 py-10">{children}</main>
      </body>
    </html>
  );
}
