import { useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  FileUp,
  Loader2,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { errorMessage, isNetworkError, uploadDocument } from "../services/api";
import type { DocumentUploadResponse } from "../types";
import { formatBytes } from "../utils/format";
import ErrorBanner from "./ErrorBanner";

export const MAX_SIZE_BYTES = 25 * 1024 * 1024;
export const MAX_SIZE_LABEL = "25 MB";
export const ALLOWED_EXTENSIONS = ["pdf", "docx", "txt"];

interface MultiDocumentUploaderProps {
  documents: DocumentUploadResponse[];
  onDocumentsChange: (documents: DocumentUploadResponse[]) => void;
  /** Optional cap on the number of documents. */
  maxDocuments?: number;
  disabled?: boolean;
}

function extensionOf(name: string): string {
  const parts = name.toLowerCase().split(".");
  return parts.length > 1 ? parts[parts.length - 1] : "";
}

interface ActiveUpload {
  key: string;
  name: string;
  phase: "uploading" | "extracting" | "error";
  message?: string;
}

/** Drag-and-drop multi-file uploader with real per-file status. */
export default function MultiDocumentUploader({
  documents,
  onDocumentsChange,
  maxDocuments = 6,
  disabled = false,
}: MultiDocumentUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [active, setActive] = useState<ActiveUpload[]>([]);
  const [issues, setIssues] = useState<string[]>([]);
  const [networkError, setNetworkError] = useState(false);
  const [retryFiles, setRetryFiles] = useState<File[]>([]);

  const handleFiles = async (files: File[]) => {
    setIssues([]);
    setNetworkError(false);
    setRetryFiles(files);
    const slots = Math.max(0, maxDocuments - documents.length);
    if (slots === 0) {
      setIssues([`You can attach at most ${maxDocuments} documents.`]);
      return;
    }

    const accepted: File[] = [];
    const rejected: string[] = [];
    files.slice(0, slots).forEach((file) => {
      const ext = extensionOf(file.name);
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        rejected.push(
          `${file.name}: unsupported type ".${ext || "?"}" (allowed: .pdf, .docx, .txt).`,
        );
      } else if (file.size > MAX_SIZE_BYTES) {
        rejected.push(
          `${file.name}: ${formatBytes(file.size)} exceeds the ${MAX_SIZE_LABEL} limit.`,
        );
      } else if (file.size === 0) {
        rejected.push(`${file.name}: the file is empty.`);
      } else {
        accepted.push(file);
      }
    });
    if (files.length > slots) {
      rejected.push(`Only ${slots} more document(s) can be attached.`);
    }
    if (rejected.length > 0) setIssues(rejected);

    const results: DocumentUploadResponse[] = [];
    for (const file of accepted) {
      const key = `${file.name}-${file.size}-${Date.now()}-${Math.random()}`;
      setActive((prev) => [...prev, { key, name: file.name, phase: "uploading" }]);
      const extractTimer = window.setTimeout(() => {
        setActive((prev) =>
          prev.map((item) =>
            item.key === key ? { ...item, phase: "extracting" } : item,
          ),
        );
      }, 450);
      try {
        const uploaded = await uploadDocument(file);
        window.clearTimeout(extractTimer);
        results.push(uploaded);
        setActive((prev) => prev.filter((item) => item.key !== key));
      } catch (err) {
        window.clearTimeout(extractTimer);
        const message = errorMessage(err);
        setActive((prev) =>
          prev.map((item) =>
            item.key === key ? { ...item, phase: "error", message } : item,
          ),
        );
        if (isNetworkError(err)) setNetworkError(true);
      }
    }
    if (results.length > 0) {
      onDocumentsChange([...documents, ...results]);
    }
  };

  const onDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length > 0) void handleFiles(files);
  };

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`relative overflow-hidden rounded-[1.25rem] border-2 border-dashed px-6 py-9 text-center transition-all duration-200 ${
          disabled
            ? "border-line bg-panel/60 opacity-70"
            : dragging
              ? "scale-[1.005] border-primary bg-teal-50/70 shadow-[0_24px_60px_-40px_rgba(13,148,136,0.9)]"
              : "border-line-strong bg-white/80 hover:border-teal-300 hover:bg-teal-50/30"
        }`}
      >
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(13,148,136,0.08),transparent_60%)]" />
        <div className="relative flex flex-col items-center">
          <span className="relative mb-3 flex h-14 w-14 items-center justify-center">
            <span className="absolute inset-0 rounded-2xl border border-teal-200/70" />
            <span className="icon-tile relative h-10 w-10">
              <UploadCloud className="h-5 w-5" aria-hidden="true" />
            </span>
          </span>
          <p className="font-display text-base font-semibold text-ink">
            Drop documents here
          </p>
          <p className="mt-1 text-sm text-muted">
            Research papers, patents, lab and prototype reports
          </p>
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
            <span className="chip">PDF</span>
            <span className="chip">DOCX</span>
            <span className="chip">TXT</span>
            <span className="chip">Max {MAX_SIZE_LABEL} each</span>
            <span className="chip">
              {documents.length}/{maxDocuments} attached
            </span>
          </div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
            className="btn btn-primary mt-5"
          >
            <FileUp className="h-4 w-4" />
            Browse files
          </button>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              if (files.length > 0) void handleFiles(files);
              e.target.value = "";
            }}
          />
        </div>
      </div>

      {issues.length > 0 && (
        <div className="mt-3 space-y-2">
          {issues.map((issue) => (
            <ErrorBanner
              key={issue}
              message={issue}
              hint={`Accepted: .pdf, .docx, .txt · Max size: ${MAX_SIZE_LABEL}`}
            />
          ))}
        </div>
      )}
      {networkError && (
        <div className="mt-3">
          <ErrorBanner
            message="The upload API is not reachable."
            networkError
            onRetry={() => void handleFiles(retryFiles)}
          />
        </div>
      )}

      {active.length > 0 && (
        <ul className="mt-3 space-y-2" aria-live="polite">
          {active.map((item) => (
            <li
              key={item.key}
              className="flex items-center gap-3 rounded-xl border border-line bg-white px-3.5 py-2.5"
            >
              {item.phase === "error" ? (
                <AlertTriangle className="h-4 w-4 shrink-0 text-rose-500" />
              ) : (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-ink">{item.name}</p>
                <p className="text-[11px] text-faint">
                  {item.phase === "uploading"
                    ? "Uploading…"
                    : item.phase === "extracting"
                      ? "Extracting text and structure…"
                      : item.message}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      {documents.length > 0 && (
        <ul className="mt-3 space-y-2">
          {documents.map((doc, index) => (
            <li
              key={doc.id}
              className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-line bg-white px-3.5 py-3"
            >
              <div className="flex min-w-0 items-start gap-2.5">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-400/20 to-teal-400/10 text-emerald-700 ring-1 ring-inset ring-emerald-500/10">
                  <FileText className="h-4 w-4" />
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <p className="truncate text-sm font-semibold text-ink">
                      {doc.original_name}
                    </p>
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200/80 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                      <CheckCircle2 className="h-3 w-3" />
                      Extracted
                    </span>
                    <span className="chip px-2 py-0 text-[10px]">
                      Document {index + 1}
                    </span>
                  </div>
                  <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-faint">
                    <span>{formatBytes(doc.size_bytes)}</span>
                    <span aria-hidden="true">·</span>
                    <span>{doc.file_type.toUpperCase()}</span>
                    <span aria-hidden="true">·</span>
                    <span>
                      {doc.page_count > 0
                        ? `${doc.page_count} page(s)`
                        : "no fixed pagination"}
                    </span>
                    <span aria-hidden="true">·</span>
                    <span>{doc.char_count.toLocaleString()} chars</span>
                    <span aria-hidden="true">·</span>
                    <span>{doc.extraction_method}</span>
                    {doc.ocr_used && (
                      <>
                        <span aria-hidden="true">·</span>
                        <span>OCR used</span>
                      </>
                    )}
                  </p>
                  {doc.warnings.length > 0 && (
                    <p className="mt-1 flex items-start gap-1 text-[11px] text-amber-700">
                      <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                      {doc.warnings.join(" ")}
                    </p>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() =>
                  onDocumentsChange(documents.filter((d) => d.id !== doc.id))
                }
                className="btn btn-ghost btn-sm shrink-0"
                aria-label={`Remove ${doc.original_name}`}
                disabled={disabled}
              >
                <Trash2 className="h-3.5 w-3.5" />
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
