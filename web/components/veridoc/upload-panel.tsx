"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowRight, Loader2 } from "lucide-react";
import AnimatedFileUpload from "@/components/smoothui/animated-file-upload";
import { Button } from "@/components/ui/button";
import { ACCEPTED_TYPES, MAX_UPLOAD_BYTES, uploadDocument } from "@/lib/api";
import { DEMO_ID } from "@/lib/demo";
import { storePreview } from "@/lib/preview";

export function UploadPanel() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!file) return;
    setBusy(true);
    try {
      const { job_id } = await uploadDocument(file);
      await storePreview(job_id, file);
      router.push(`/jobs/?id=${encodeURIComponent(job_id)}`);
    } catch (err) {
      toast.error("Upload failed", {
        description:
          err instanceof Error && err.message !== "Failed to fetch"
            ? err.message
            : "The API is unreachable. It may still be waking up; try again in a minute.",
      });
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <AnimatedFileUpload
        accept={ACCEPTED_TYPES}
        maxSize={MAX_UPLOAD_BYTES}
        multiple={false}
        disabled={busy}
        onFilesSelected={(files) => setFile(files[0] ?? null)}
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button size="lg" onClick={submit} disabled={!file || busy} className="active:scale-[0.98]">
          {busy ? <Loader2 className="animate-spin" /> : null}
          {busy ? "Uploading" : "Extract fields"}
          {!busy && <ArrowRight />}
        </Button>
        <Link
          href={`/jobs/?id=${DEMO_ID}`}
          className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          No file handy? Open the sample invoice
        </Link>
      </div>
      <p className="text-xs text-muted-foreground">
        PDF, PNG or JPG up to 10 MB. The original file is deleted after extraction; account numbers
        are masked before anything is stored.
      </p>
    </div>
  );
}
