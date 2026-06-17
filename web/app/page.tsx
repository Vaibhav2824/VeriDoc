"use client";

import { useRouter } from "next/navigation";
import { useState, useRef } from "react";
import { uploadDocument } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setError(null);
    setLoading(true);
    try {
      const { job_id } = await uploadDocument(file);
      router.push(`/jobs/${job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center gap-10 pt-10">
      <div className="text-center space-y-3">
        <h1 className="text-4xl font-bold tracking-tight">VeriDoc</h1>
        <p className="text-gray-500 text-lg max-w-lg">
          Upload an invoice or bank statement. Every extracted field gets a
          calibrated confidence score — low-confidence fields are flagged for
          review instead of hallucinated.
        </p>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files[0];
          if (file) handleFile(file);
        }}
        className={`
          w-full max-w-xl border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer
          transition-colors select-none
          ${dragging ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-gray-400 bg-white"}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
        {loading ? (
          <p className="text-blue-600 font-medium">Uploading…</p>
        ) : (
          <>
            <p className="text-2xl mb-2">📄</p>
            <p className="font-medium text-gray-700">Drop a PDF or image here</p>
            <p className="text-sm text-gray-400 mt-1">or click to browse</p>
            <p className="text-xs text-gray-400 mt-3">Supports: PDF, PNG, JPG</p>
          </>
        )}
      </div>

      {error && (
        <div className="text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Feature bullets */}
      <div className="grid grid-cols-3 gap-6 w-full max-w-xl text-sm text-gray-600">
        {[
          ["🔍", "Source-grounded", "Every value linked to its exact source location"],
          ["📊", "Calibrated confidence", "ECE-tested scores per field"],
          ["🚫", "Abstention gate", "Low-confidence fields routed to review, never hallucinated"],
        ].map(([icon, title, desc]) => (
          <div key={title} className="bg-white rounded-xl border p-4 space-y-1">
            <span className="text-xl">{icon}</span>
            <p className="font-semibold text-gray-800">{title}</p>
            <p>{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
