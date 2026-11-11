import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Cpu,
  FileText,
  FileUp,
  Layers,
  Loader2,
  Play,
  ScanText,
  Settings2,
  Sparkles,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { analyzeDocuments, errorMessage, isNetworkError } from "../services/api";
import { useApi } from "../hooks/useApi";
import type {
  AnalyzeRequest,
  AssessmentResult,
  CapabilitiesResponse,
  DocumentInfo,
  DocumentUploadResponse,
  OverviewResponse,
} from "../types";
import PageHeader from "../components/PageHeader";
import ErrorBanner, { WarningBanner } from "../components/ErrorBanner";
import EmptyState from "../components/EmptyState";
import MultiDocumentUploader from "../components/MultiDocumentUploader";
import AssessmentProcessingTimeline from "../components/AssessmentProcessingTimeline";
import { formatBytes, formatDate } from "../utils/format";

const MAX_DOCS = 6;
const STEPS = ["Documents", "Details", "Review", "Configure", "Processing"];

const ANALYZE_STAGES = [
  {
    id: "documents",
    label: "Loading document text",
    detail: "Reading the stored extracts for every attached document.",
  },
  {
    id: "evidence",
    label: "Extracting evidence",
    detail: "Locating completed, proposed and contradictory statements.",
  },
  {
    id: "retrieval",
    label: "Ranking evidence",
    detail: "Matching excerpts to milestones with the configured retrieval backend.",
  },
  {
    id: "milestones",
    label: "Verifying milestones",
    detail: "Cross-checking each milestone against supporting excerpts.",
  },
  {
    id: "contradictions",
    label: "Detecting contradictions",
    detail: "Comparing conflicting statements across documents and time.",
  },
  {
    id: "roadmap",
    label: "Building roadmap and questionnaire",
    detail: "Deriving next-step actions and missing-evidence questions.",
  },
  {
    id: "report",
    label: "Writing the assessment",
    detail: "Persisting the prediction, evidence and report artefacts.",
  },
];

type AttachedDocument = {
  id: string;
  name: string;
  pages: number;
  chars: number;
  uploadedAt: string | null;
  fileType: string;
  source: "upload" | "library";
};

function guessTechnologyName(filename: string): string {
  return filename
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .trim();
}

function CheckRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line/70 py-2.5 last:border-0">
      <span className="text-xs text-muted">{label}</span>
      <span className="min-w-0 break-words text-right text-xs font-semibold text-ink">
        {value}
      </span>
    </div>
  );
}

export default function NewAssessment() {
  const navigate = useNavigate();
  const overview = useApi<OverviewResponse>("/api/overview");
  const library = useApi<DocumentInfo[]>("/api/documents");
  const capabilities = useApi<CapabilitiesResponse>("/api/system/capabilities");

  const [step, setStep] = useState(0);
  const [uploadedDocs, setUploadedDocs] = useState<DocumentUploadResponse[]>([]);
  const [libraryDocs, setLibraryDocs] = useState<DocumentInfo[]>([]);

  // Metadata form
  const [techName, setTechName] = useState("");
  const [domain, setDomain] = useState("");
  const [organization, setOrganization] = useState("");
  const [description, setDescription] = useState("");

  // Configuration
  const [multiDocument, setMultiDocument] = useState(true);
  const [primaryId, setPrimaryId] = useState("");

  // Analysis
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [analyzeNetwork, setAnalyzeNetwork] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);

  const domains = overview.data?.domains ?? [];

  const attached = useMemo<AttachedDocument[]>(
    () => [
      ...uploadedDocs.map((d) => ({
        id: d.id,
        name: d.original_name,
        pages: d.page_count,
        chars: d.char_count,
        uploadedAt: d.uploaded_at ?? null,
        fileType: d.file_type,
        source: "upload" as const,
      })),
      ...libraryDocs.map((d) => ({
        id: d.id,
        name: d.original_name,
        pages: d.page_count,
        chars: d.char_count,
        uploadedAt: d.uploaded_at ?? null,
        fileType: d.file_type,
        source: "library" as const,
      })),
    ],
    [uploadedDocs, libraryDocs],
  );

  // Keep a valid primary document selected.
  useEffect(() => {
    if (attached.length === 0) {
      if (primaryId) setPrimaryId("");
      return;
    }
    if (!attached.some((d) => d.id === primaryId)) {
      setPrimaryId(attached[0].id);
    }
  }, [attached, primaryId]);

  useEffect(() => {
    if (!analyzing) return;
    const id = window.setInterval(
      () =>
        setStageIndex((i) => Math.min(i + 1, ANALYZE_STAGES.length - 1)),
      1500,
    );
    return () => window.clearInterval(id);
  }, [analyzing]);

  const handleUploadedChange = useCallback(
    (docs: DocumentUploadResponse[]) => {
      setUploadedDocs(docs);
      if (docs.length > 0) {
        setTechName(
          (current) =>
            current || guessTechnologyName(docs[0].original_name || ""),
        );
      }
    },
    [],
  );

  const addLibraryDoc = (doc: DocumentInfo) => {
    setLibraryDocs((current) => {
      if (current.some((d) => d.id === doc.id)) return current;
      return [...current, doc];
    });
    setTechName(
      (current) => current || guessTechnologyName(doc.original_name || ""),
    );
  };

  const removeLibraryDoc = (id: string) =>
    setLibraryDocs((current) => current.filter((d) => d.id !== id));

  const resetAll = () => {
    setUploadedDocs([]);
    setLibraryDocs([]);
    setTechName("");
    setDomain("");
    setOrganization("");
    setDescription("");
    setMultiDocument(true);
    setPrimaryId("");
    setStep(0);
    setAnalyzeError(null);
    setAnalyzeNetwork(false);
    setAnalyzing(false);
  };

  const runAnalysis = async () => {
    if (attached.length === 0 || !techName.trim()) return;
    setAnalyzing(true);
    setAnalyzeError(null);
    setAnalyzeNetwork(false);
    setStageIndex(0);
    setStep(4);
    try {
      const body: AnalyzeRequest = {
        technology_name: techName.trim(),
        domain: domain.trim(),
        organization: organization.trim(),
        description: description.trim(),
      };
      if (attached.length > 1 && multiDocument) {
        body.document_ids = attached.map((d) => d.id);
      } else {
        body.document_id = primaryId || attached[0].id;
      }
      const result: AssessmentResult = await analyzeDocuments(body);
      setStageIndex(ANALYZE_STAGES.length);
      navigate(`/assessments/${result.id}`);
    } catch (err) {
      setAnalyzing(false);
      setAnalyzeError(errorMessage(err));
      setAnalyzeNetwork(isNetworkError(err));
    }
  };

  const currentStep = step + 1;
  const canContinue =
    step === 0
      ? attached.length > 0
      : step === 1
        ? techName.trim().length > 0
        : true;

  const analysisScope =
    attached.length > 1 && multiDocument
      ? `${attached.length} documents synthesised together`
      : primaryId
        ? `Single document: ${attached.find((d) => d.id === primaryId)?.name ?? "primary document"}`
        : "Single document";

  return (
    <div className="max-w-5xl">
      <PageHeader
        title="New Assessment"
        subtitle="Attach one or more technical documents and run a full TRL 1–9 assessment."
        actions={
          <span className="chip">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Evidence-based · no invented metrics
          </span>
        }
      />

      {/* Stepper */}
      <ol className="card mb-5 flex items-center gap-1.5 px-3 py-2.5 sm:gap-3 sm:px-4">
        {STEPS.map((label, i) => {
          const n = i + 1;
          const done = n < currentStep;
          const active = n === currentStep;
          const reachable = !analyzing && n <= 4;
          return (
            <li
              key={label}
              className="flex min-w-0 flex-1 items-center gap-1.5 sm:gap-2.5"
              aria-current={active ? "step" : undefined}
            >
              <button
                type="button"
                disabled={!reachable || n - 1 > step}
                onClick={() => {
                  if (reachable && n - 1 < step) setStep(n - 1);
                }}
                className="flex items-center gap-2 disabled:cursor-default"
                title={reachable ? `Go to ${label}` : label}
              >
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold transition-colors ${
                    done
                      ? "border-teal-500 bg-teal-500 text-white"
                      : active
                        ? "border-primary bg-teal-50 text-primary-dark ring-4 ring-teal-500/10"
                        : "border-line-strong bg-white text-faint"
                  }`}
                >
                  {done ? <CheckCircle2 className="h-4 w-4" /> : n}
                </span>
                <span
                  className={`hidden truncate text-xs font-semibold sm:block ${
                    active ? "text-ink" : done ? "text-muted" : "text-faint"
                  }`}
                >
                  {label}
                </span>
              </button>
              {i < STEPS.length - 1 && (
                <span
                  className={`h-px min-w-2 flex-1 ${
                    done ? "bg-teal-300" : "bg-line"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>

      {/* 1 — Documents */}
      {step === 0 && (
        <div className="space-y-4">
          <div className="card p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <span className="icon-tile h-9 w-9 shrink-0">
                <UploadCloud className="h-4 w-4" />
              </span>
              <div>
                <h2 className="section-title">Attach documents</h2>
                <p className="mt-0.5 text-xs text-faint">
                  PDF, DOCX or TXT · up to {MAX_DOCS} documents · max 25 MB each.
                  Multiple documents are compared for duplicates, conflicts and
                  outdated claims.
                </p>
              </div>
            </div>
            <div className="mt-5">
              <MultiDocumentUploader
                documents={uploadedDocs}
                onDocumentsChange={handleUploadedChange}
                maxDocuments={Math.max(0, MAX_DOCS - libraryDocs.length)}
                disabled={analyzing}
              />
            </div>
          </div>

          {/* Reuse from the document library */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="icon-tile h-9 w-9 shrink-0">
                  <Layers className="h-4 w-4" />
                </span>
                <div>
                  <h2 className="section-title">Document library</h2>
                  <p className="mt-0.5 text-xs text-faint">
                    Reuse documents that were already uploaded to this workspace.
                  </p>
                </div>
              </div>
              <span className="chip">
                {libraryDocs.length} attached from library
              </span>
            </div>
            <div className="p-5">
              {library.loading && !library.data ? (
                <p className="text-sm text-faint">Loading documents…</p>
              ) : library.error ? (
                <ErrorBanner
                  message={library.error}
                  networkError={library.networkError}
                  onRetry={library.refetch}
                />
              ) : (library.data ?? []).length === 0 ? (
                <p className="text-sm text-faint">
                  No previously uploaded documents. Upload one above to start the
                  library.
                </p>
              ) : (
                <ul className="divide-y divide-line/70">
                  {(library.data ?? []).map((doc) => {
                    const selected = libraryDocs.some((d) => d.id === doc.id);
                    return (
                      <li
                        key={doc.id}
                        className="flex flex-wrap items-center gap-3 py-3"
                      >
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line bg-panel text-muted">
                          <FileText className="h-4 w-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-ink">
                            {doc.original_name}
                          </span>
                          <span className="block truncate text-xs text-faint">
                            {doc.file_type.toUpperCase()} ·{" "}
                            {doc.page_count > 0
                              ? `${doc.page_count} page(s)`
                              : "no fixed pagination"}{" "}
                            · {formatBytes(doc.size_bytes)} ·{" "}
                            {formatDate(doc.uploaded_at)}
                          </span>
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            selected
                              ? removeLibraryDoc(doc.id)
                              : addLibraryDoc(doc)
                          }
                          disabled={
                            !selected &&
                            libraryDocs.length + uploadedDocs.length >= MAX_DOCS
                          }
                          className={`btn btn-sm ${
                            selected ? "btn-secondary" : "btn-primary"
                          }`}
                          aria-pressed={selected}
                        >
                          {selected ? (
                            <>
                              <Trash2 className="h-3.5 w-3.5" />
                              Remove
                            </>
                          ) : (
                            <>
                              <FileUp className="h-3.5 w-3.5" />
                              Attach
                            </>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>

          {/* Attached summary */}
          <div className="card overflow-hidden">
            <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
              <h3 className="section-title">Attached ({attached.length})</h3>
              {attached.length > 0 && (
                <button
                  type="button"
                  onClick={resetAll}
                  className="text-xs font-semibold text-muted hover:text-danger"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="p-5">
              {attached.length === 0 ? (
                <p className="text-sm text-faint">
                  Nothing attached yet. Upload a document or pick one from the
                  library.
                </p>
              ) : (
                <ul className="space-y-2">
                  {attached.map((doc) => (
                    <li
                      key={doc.id}
                      className="flex items-center gap-3 rounded-xl border border-line bg-panel/60 px-3 py-2.5"
                    >
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                      <span className="min-w-0 flex-1 truncate text-sm text-ink-soft">
                        {doc.name}
                      </span>
                      <span className="chip shrink-0">
                        {doc.source === "library" ? "Library" : "Uploaded"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 2 — Details */}
      {step === 1 && (
        <div className="card p-5 sm:p-6">
          <div className="flex items-start gap-3">
            <span className="icon-tile h-9 w-9 shrink-0">
              <ScanText className="h-4 w-4" />
            </span>
            <div>
              <h2 className="section-title">Technology details</h2>
              <p className="mt-0.5 text-xs text-faint">
                Used for the report header, history, comparison and gap analysis.
              </p>
            </div>
          </div>
          <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="tech-name" className="label">
                Technology name <span className="text-danger">*</span>
              </label>
              <input
                id="tech-name"
                type="text"
                value={techName}
                onChange={(e) => setTechName(e.target.value)}
                placeholder="e.g. Solar Membrane Distillation Unit"
                className="input"
                autoFocus
              />
            </div>
            <div>
              <label htmlFor="tech-domain" className="label">
                Technology domain
              </label>
              <input
                id="tech-domain"
                type="text"
                list="domain-options"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="e.g. Water Treatment"
                className="input"
              />
              <datalist id="domain-options">
                {domains.map((d) => (
                  <option key={d} value={d} />
                ))}
              </datalist>
            </div>
            <div>
              <label htmlFor="tech-org" className="label">
                Organization
              </label>
              <input
                id="tech-org"
                type="text"
                value={organization}
                onChange={(e) => setOrganization(e.target.value)}
                placeholder="e.g. Energy Research Lab"
                className="input"
              />
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="tech-desc" className="label">
                Research description
              </label>
              <textarea
                id="tech-desc"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Short description of the technology and its intended application…"
                className="textarea"
              />
            </div>
          </div>
          {!techName.trim() && (
            <p className="mt-4 inline-flex items-center gap-1.5 text-xs text-warning">
              <AlertTriangle className="h-3.5 w-3.5" />
              A technology name is required before continuing.
            </p>
          )}
        </div>
      )}

      {/* 3 — Review */}
      {step === 2 && (
        <div className="space-y-4">
          <div className="card overflow-hidden">
            <div className="flex items-center gap-3 border-b border-line px-5 py-4">
              <span className="icon-tile h-9 w-9 shrink-0">
                <FileText className="h-4 w-4" />
              </span>
              <div>
                <h2 className="section-title">Document review</h2>
                <p className="mt-0.5 text-xs text-faint">
                  Check what will be sent to the assessment pipeline.
                </p>
              </div>
            </div>
            <div className="space-y-3 p-5">
              {uploadedDocs.map((doc) => (
                <details
                  key={doc.id}
                  className="rounded-xl border border-line bg-white px-4 py-3"
                >
                  <summary className="cursor-pointer text-sm font-semibold text-ink">
                    {doc.original_name}{" "}
                    <span className="font-normal text-faint">
                      · {doc.char_count.toLocaleString()} chars
                    </span>
                  </summary>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-xs text-faint">
                    <span className="chip">
                      {doc.page_count > 0
                        ? `${doc.page_count} page(s)`
                        : "no fixed pagination"}
                    </span>
                    <span className="chip">{doc.extraction_method}</span>
                    {doc.ocr_used && <span className="chip">OCR used</span>}
                    {doc.has_tables && <span className="chip">Tables</span>}
                  </div>
                  {doc.warnings.length > 0 && (
                    <div className="mt-3 space-y-2">
                      {doc.warnings.map((w) => (
                        <WarningBanner key={w} message={w} />
                      ))}
                    </div>
                  )}
                  {doc.headings.length > 0 && (
                    <div className="mt-3">
                      <p className="eyebrow mb-1.5">Detected headings</p>
                      <div className="flex flex-wrap gap-1.5">
                        {doc.headings.slice(0, 12).map((h, i) => (
                          <span key={`${h}-${i}`} className="chip">
                            {h}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <pre className="scrollbar-thin mt-3 max-h-52 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-panel p-3 font-sans text-[12.5px] leading-relaxed text-ink-soft">
                    {doc.preview_text || "(no text preview available)"}
                  </pre>
                </details>
              ))}
              {libraryDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="rounded-xl border border-line bg-white px-4 py-3"
                >
                  <p className="text-sm font-semibold text-ink">
                    {doc.original_name}{" "}
                    <span className="font-normal text-faint">
                      · reused from library
                    </span>
                  </p>
                  <p className="mt-1 text-xs text-faint">
                    {doc.page_count > 0
                      ? `${doc.page_count} page(s)`
                      : "no fixed pagination"}{" "}
                    · {doc.char_count.toLocaleString()} characters
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="border-b border-line px-5 py-4">
              <h2 className="section-title">Assessment inputs</h2>
            </div>
            <div className="px-5 py-2">
              <CheckRow label="Technology" value={techName || "—"} />
              <CheckRow label="Domain" value={domain || "—"} />
              <CheckRow label="Organization" value={organization || "—"} />
              <CheckRow
                label="Documents"
                value={`${attached.length} attached`}
              />
              <CheckRow label="Description" value={description || "—"} />
            </div>
          </div>

          <div className="card p-5">
            <h2 className="section-title">What will be generated</h2>
            <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {[
                "Traceable evidence excerpts with page/section locators",
                "Milestone-by-milestone verification",
                "TRL prediction with alternatives and uncertainty",
                "Cross-document contradictions and duplicate handling",
                "Evidence knowledge graph",
                "Roadmap, questionnaire and expert-review workflow",
              ].map((item) => (
                <li
                  key={item}
                  className="flex items-start gap-2 text-sm leading-relaxed text-muted"
                >
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* 4 — Configure */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="card overflow-hidden">
            <div className="flex items-center gap-3 border-b border-line px-5 py-4">
              <span className="icon-tile h-9 w-9 shrink-0">
                <Settings2 className="h-4 w-4" />
              </span>
              <div>
                <h2 className="section-title">Analysis configuration</h2>
                <p className="mt-0.5 text-xs text-faint">
                  These choices map directly to the analysis request.
                </p>
              </div>
            </div>
            <div className="space-y-5 p-5">
              <fieldset>
                <legend className="label">Analysis scope</legend>
                <div className="mt-2 space-y-2">
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 ${
                      multiDocument && attached.length > 1
                        ? "border-primary bg-teal-50/40"
                        : "border-line bg-white"
                    } ${attached.length <= 1 ? "opacity-60" : ""}`}
                  >
                    <input
                      type="radio"
                      name="scope"
                      checked={multiDocument && attached.length > 1}
                      disabled={attached.length <= 1}
                      onChange={() => setMultiDocument(true)}
                      className="mt-0.5 h-4 w-4 accent-teal-600"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-ink">
                        Multi-document synthesis
                      </span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-muted">
                        Analyse all {attached.length} documents together, deduplicate
                        repeated claims and surface cross-document conflicts.
                      </span>
                    </span>
                  </label>
                  <label
                    className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3 ${
                      !multiDocument || attached.length <= 1
                        ? "border-primary bg-teal-50/40"
                        : "border-line bg-white"
                    }`}
                  >
                    <input
                      type="radio"
                      name="scope"
                      checked={!multiDocument || attached.length <= 1}
                      onChange={() => setMultiDocument(false)}
                      className="mt-0.5 h-4 w-4 accent-teal-600"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-ink">
                        Single document
                      </span>
                      <span className="mt-0.5 block text-xs leading-relaxed text-muted">
                        Assess one primary document; other attachments are ignored.
                      </span>
                    </span>
                  </label>
                </div>
              </fieldset>

              {(!multiDocument || attached.length <= 1) && attached.length > 0 && (
                <div>
                  <label htmlFor="primary-document" className="label">
                    Primary document
                  </label>
                  <select
                    id="primary-document"
                    value={primaryId}
                    onChange={(e) => setPrimaryId(e.target.value)}
                    className="select mt-2"
                  >
                    {attached.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="rounded-xl border border-line bg-panel/60 px-4 py-3">
                <p className="eyebrow mb-1.5">Effective request</p>
                <p className="text-sm text-ink-soft">{analysisScope}</p>
                <p className="mt-1 text-xs text-faint">
                  Technology: {techName || "—"}
                  {domain ? ` · Domain: ${domain}` : ""}
                </p>
              </div>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="flex items-center gap-3 border-b border-line px-5 py-4">
              <span className="icon-tile h-9 w-9 shrink-0">
                <Cpu className="h-4 w-4" />
              </span>
              <div>
                <h2 className="section-title">Runtime capabilities</h2>
                <p className="mt-0.5 text-xs text-faint">
                  Reported by the running server; optional packages fall back
                  automatically.
                </p>
              </div>
            </div>
            <div className="px-5 py-2">
              {capabilities.loading && !capabilities.data ? (
                <p className="py-4 text-sm text-faint">Reading capabilities…</p>
              ) : capabilities.error && !capabilities.data ? (
                <div className="py-4">
                  <ErrorBanner
                    message={capabilities.error}
                    networkError={capabilities.networkError}
                    onRetry={capabilities.refetch}
                  />
                </div>
              ) : capabilities.data ? (
                <>
                  <CheckRow
                    label="Document parser"
                    value={`${capabilities.data.parser.active} (configured: ${capabilities.data.parser.configured})`}
                  />
                  <CheckRow
                    label="Docling available"
                    value={
                      capabilities.data.parser.docling_available ? "Yes" : "No"
                    }
                  />
                  <CheckRow
                    label="Embedding backend"
                    value={`${capabilities.data.embeddings.active} · ${
                      capabilities.data.embeddings.model || "default"
                    }`}
                  />
                  <CheckRow
                    label="Semantic retrieval"
                    value={
                      capabilities.data.semantic_retrieval.enabled
                        ? `Enabled · ${capabilities.data.semantic_retrieval.backend}`
                        : "Disabled"
                    }
                  />
                  <CheckRow
                    label="Neural embeddings available"
                    value={capabilities.data.embeddings.available ? "Yes" : "No"}
                  />
                  <CheckRow
                    label="BGE (FlagEmbedding) installed"
                    value={
                      capabilities.data.embeddings.flag_embedding_installed
                        ? "Yes"
                        : "No"
                    }
                  />
                  <CheckRow
                    label="SHAP explanations"
                    value={
                      capabilities.data.shap.installed
                        ? capabilities.data.shap.enabled
                          ? "Installed · enabled"
                          : "Installed · disabled"
                        : "Not installed (linear fallback)"
                    }
                  />
                  <CheckRow
                    label="Embedding fallback"
                    value={capabilities.data.embeddings.fallback_reason || "—"}
                  />
                </>
              ) : (
                <p className="py-4 text-sm text-faint">
                  Capability report unavailable.
                </p>
              )}
            </div>
          </div>

          {analyzeError && (
            <ErrorBanner
              message={analyzeError}
              networkError={analyzeNetwork}
              onRetry={() => void runAnalysis()}
            />
          )}
        </div>
      )}

      {/* 5 — Processing */}
      {step === 4 && (
        <div className="space-y-4">
          <div className="card p-5 sm:p-6">
            <div className="flex items-start gap-3">
              <span className="icon-tile h-9 w-9 shrink-0">
                {analyzing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
              </span>
              <div>
                <h2 className="section-title">
                  {analyzing ? "Running assessment…" : "Assessment stopped"}
                </h2>
                <p className="mt-0.5 text-xs text-faint">
                  {techName || "Untitled technology"} · {analysisScope}
                </p>
              </div>
            </div>

            <div className="mt-5">
              <AssessmentProcessingTimeline
                stages={ANALYZE_STAGES.map((stage, i) => ({
                  ...stage,
                  status: !analyzing
                    ? "pending"
                    : i < stageIndex
                      ? "done"
                      : i === stageIndex
                        ? "active"
                        : "pending",
                }))}
                note="The backend runs these stages synchronously; progress indicators are approximate, not measured step events."
              />
            </div>

            {analyzeError && (
              <div className="mt-4 space-y-3">
                <ErrorBanner
                  message={analyzeError}
                  networkError={analyzeNetwork}
                  onRetry={() => void runAnalysis()}
                />
                <button
                  type="button"
                  onClick={() => {
                    setAnalyzeError(null);
                    setStep(3);
                  }}
                  className="btn btn-secondary"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Back to configuration
                </button>
              </div>
            )}
          </div>

          {attached.length === 0 && (
            <EmptyState
              title="No documents attached"
              description="Go back to the documents step and attach at least one file."
              actionLabel="Choose documents"
              onAction={() => setStep(0)}
            />
          )}
        </div>
      )}

      {/* Footer navigation */}
      {step < 4 && (
        <div className="card mt-4 flex flex-wrap items-center justify-between gap-3 p-4">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            className="btn btn-secondary"
          >
            <ChevronLeft className="h-4 w-4" />
            Back
          </button>
          <div className="flex items-center gap-3">
            <span className="text-xs text-faint">
              {step === 0
                ? `${attached.length} document${attached.length === 1 ? "" : "s"} attached`
                : step === 1
                  ? techName.trim()
                    ? "Details ready"
                    : "Technology name required"
                  : step === 2
                    ? `Step ${currentStep} of 5`
                    : `Step ${currentStep} of 5`}
            </span>
            {step < 3 ? (
              <button
                type="button"
                onClick={() => setStep((s) => Math.min(3, s + 1))}
                disabled={!canContinue}
                className="btn btn-primary"
              >
                Continue
                <ChevronRight className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void runAnalysis()}
                disabled={attached.length === 0 || !techName.trim() || analyzing}
                className="btn btn-primary btn-lg"
              >
                <Play className="h-4 w-4" />
                Run assessment
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
