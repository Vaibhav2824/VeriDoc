/**
 * In-browser document previews, keyed by job id. Previews never leave the
 * browser (PII guardrail) and only live for this tab's session.
 */
const previews = new Map<string, string[]>();

export const getPreview = (jobId: string) => previews.get(jobId);

const MAX_PAGES = 5;

export async function storePreview(jobId: string, file: File): Promise<void> {
  if (file.type.startsWith("image/")) {
    previews.set(jobId, [URL.createObjectURL(file)]);
    return;
  }
  if (file.type !== "application/pdf") return;
  try {
    const pdfjs = await import("pdfjs-dist");
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/build/pdf.worker.min.mjs",
      import.meta.url,
    ).toString();
    const doc = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
    const pages: string[] = [];
    for (let i = 1; i <= Math.min(doc.numPages, MAX_PAGES); i++) {
      const page = await doc.getPage(i);
      const viewport = page.getViewport({ scale: 1.5 });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvas, viewport }).promise;
      pages.push(canvas.toDataURL("image/png"));
    }
    previews.set(jobId, pages);
  } catch (err) {
    // Preview is a nicety; extraction results still render without it.
    console.warn("PDF preview failed", err);
  }
}
