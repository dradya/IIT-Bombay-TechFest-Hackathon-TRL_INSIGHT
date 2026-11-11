import { useState } from "react";
import {
  CheckCircle2,
  Cpu,
  Database,
  ExternalLink,
  FileText,
  Plug,
  Server,
  Settings as SettingsIcon,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { apiGet, errorMessage } from "../services/api";
import type {
  CapabilitiesResponse,
  HealthResponse,
  TRLReferenceResponse,
} from "../types";
import PageHeader from "../components/PageHeader";
import ErrorBanner from "../components/ErrorBanner";
import StatusBadge from "../components/StatusBadge";
import Skeleton from "../components/Skeleton";
import {
  readDefaultEvidenceFilter,
  writeDefaultEvidenceFilter,
} from "../utils/prefs";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line/70 py-3 last:border-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="min-w-0 break-all text-right text-sm font-medium text-ink">
        {value}
      </span>
    </div>
  );
}

function CardHeader({
  icon: Icon,
  title,
  subtitle,
}: {
  icon: typeof SettingsIcon;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="flex items-center gap-3 border-b border-line px-5 py-4">
      <span className="icon-tile h-9 w-9 shrink-0">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <h2 className="section-title">{title}</h2>
        <p className="mt-0.5 text-xs text-faint">{subtitle}</p>
      </div>
    </div>
  );
}

export default function Settings() {
  const health = useApi<HealthResponse>("/api/health");
  const reference = useApi<TRLReferenceResponse>("/api/trl/reference");
  const capabilities = useApi<CapabilitiesResponse>("/api/system/capabilities");

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    ok: boolean;
    message: string;
    at: string;
  } | null>(null);

  // The only real preference: default evidence filter for the result page,
  // stored in localStorage (shared with EvidenceTable via utils/prefs).
  const [defaultFilter, setDefaultFilter] = useState<string>(() =>
    readDefaultEvidenceFilter(),
  );

  const changeDefaultFilter = (value: string) => {
    setDefaultFilter(value);
    writeDefaultEvidenceFilter(value);
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      const res = await apiGet<HealthResponse>("/api/health");
      setTestResult({
        ok: res.status === "ok",
        message: `Connected — ${res.app} v${res.version} (${res.environment})`,
        at: new Date().toLocaleString(),
      });
    } catch (err) {
      setTestResult({
        ok: false,
        message: errorMessage(err),
        at: new Date().toLocaleString(),
      });
    } finally {
      setTesting(false);
    }
  };

  const h = health.data;
  const ref = reference.data;
  const caps = capabilities.data;
  const rules = ref?.assessment_rules ?? {};
  const maxUpload = rules.max_upload_size_mb ?? 25;
  const allowedTypes = Array.isArray(rules.allowed_file_types)
    ? (rules.allowed_file_types as string[]).join(", ")
    : ".pdf, .docx, .txt";

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Settings"
        subtitle="System information, connection status and local preferences."
        actions={
          <button
            type="button"
            onClick={() => void testConnection()}
            disabled={testing}
            className="btn btn-primary"
          >
            <Plug className="h-4 w-4" />
            {testing ? "Testing…" : "Test connection"}
          </button>
        }
      />

      {testResult && (
        <div
          className={`mb-4 flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm shadow-[0_1px_2px_rgba(10,22,40,0.04)] ${
            testResult.ok
              ? "border-emerald-200/80 bg-emerald-50 text-emerald-900"
              : "border-rose-200/80 bg-rose-50 text-rose-900"
          }`}
          role="status"
        >
          {testResult.ok ? (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          ) : (
            <Plug className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
          )}
          <div>
            <p className="font-semibold">{testResult.message}</p>
            <p className="mt-0.5 text-xs opacity-70">Checked at {testResult.at}</p>
          </div>
        </div>
      )}

      {health.error && !health.data && (
        <div className="mb-4">
          <ErrorBanner
            message={health.error}
            networkError={health.networkError}
            onRetry={health.refetch}
          />
        </div>
      )}

      {/* Application */}
      <div className="card overflow-hidden">
        <CardHeader
          icon={SettingsIcon}
          title="Application"
          subtitle="Runtime information from /api/health"
        />
        <div className="px-5 py-2">
          {health.loading && !h ? (
            <div className="space-y-3 py-3">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-2/3" />
            </div>
          ) : h ? (
            <>
              <Row label="App" value={`${h.app}`} />
              <Row label="Version" value={h.version} />
              <Row label="Environment" value={h.environment} />
              <Row label="API base URL" value={window.location.origin} />
              <Row
                label="Database"
                value={
                  <code className="rounded-md bg-panel px-1.5 py-0.5 text-xs">
                    {h.database}
                  </code>
                }
              />
              <Row
                label="Model"
                value={
                  <span className="inline-flex items-center gap-2">
                    {h.model_mode}
                    <StatusBadge
                      kind="custom"
                      value=""
                      tone={h.model_available ? "green" : "amber"}
                      label={h.model_available ? "Available" : "Rule-only mode"}
                    />
                  </span>
                }
              />
              <Row
                label="Last health check"
                value={
                  <span className="inline-flex items-center gap-2">
                    {new Date(h.time).toLocaleString()}
                    <button
                      type="button"
                      onClick={health.refetch}
                      className="text-xs font-semibold text-primary hover:text-primary-dark"
                    >
                      Refresh
                    </button>
                  </span>
                }
              />
            </>
          ) : (
            <p className="py-4 text-sm text-faint">Backend not reachable.</p>
          )}
        </div>
      </div>

      {/* Framework */}
      <div className="card mt-4 overflow-hidden">
        <CardHeader
          icon={Database}
          title="Assessment framework"
          subtitle="From /api/trl/reference (live, never hardcoded)"
        />
        <div className="px-5 py-2">
          {reference.loading && !ref ? (
            <div className="space-y-3 py-3">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-1/2" />
            </div>
          ) : ref ? (
            <>
              <Row label="Framework version" value={ref.version} />
              <Row label="TRL levels" value={ref.levels.length} />
              <Row label="Milestones" value={ref.milestones.length} />
              <Row
                label="Evidence categories"
                value={ref.evidence_categories.length}
              />
              <Row
                label="Evidence statuses"
                value={ref.evidence_statuses.join(", ")}
              />
              <Row label="Max upload size" value={`${maxUpload} MB`} />
              <Row label="Allowed file types" value={allowedTypes} />
              <Row
                label="Low-confidence threshold"
                value={
                  rules.low_confidence_threshold !== undefined
                    ? `${Number(rules.low_confidence_threshold) * 100}%`
                    : "—"
                }
              />
            </>
          ) : (
            <p className="py-4 text-sm text-faint">
              Reference framework not loaded.
            </p>
          )}
        </div>
      </div>

      {/* Optional OSS integrations */}
      <div className="card mt-4 overflow-hidden">
        <CardHeader
          icon={Cpu}
          title="Optional integrations"
          subtitle="Actual availability from /api/system/capabilities — native fallbacks stay active"
        />
        <div className="px-5 py-2">
          {capabilities.loading && !caps ? (
            <div className="space-y-3 py-3">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-5 w-1/2" />
            </div>
          ) : capabilities.error && !caps ? (
            <div className="py-4">
              <ErrorBanner
                message={capabilities.error}
                networkError={capabilities.networkError}
                onRetry={capabilities.refetch}
              />
            </div>
          ) : caps ? (
            <>
              <Row
                label="Document parser"
                value={
                  <span>
                    {caps.parser.active}
                    <span className="ml-1 text-xs font-normal text-faint">
                      · configured {caps.parser.configured}
                    </span>
                  </span>
                }
              />
              <Row
                label="Docling (structured parsing)"
                value={
                  <StatusBadge
                    kind="custom"
                    value=""
                    tone={caps.parser.docling_available ? "green" : "amber"}
                    label={
                      caps.parser.docling_available
                        ? "Available"
                        : "Not installed"
                    }
                  />
                }
              />
              <Row
                label="Parser native fallback"
                value={caps.parser.native_fallback}
              />
              <Row
                label="Embedding backend"
                value={
                  <span>
                    {caps.embeddings.active}
                    <span className="ml-1 text-xs font-normal text-faint">
                      · {caps.embeddings.model || "default"}
                    </span>
                  </span>
                }
              />
              <Row
                label="Semantic retrieval"
                value={
                  <StatusBadge
                    kind="custom"
                    value=""
                    tone={
                      caps.semantic_retrieval.enabled ? "green" : "amber"
                    }
                    label={
                      caps.semantic_retrieval.enabled
                        ? `Enabled · ${caps.semantic_retrieval.backend}`
                        : "Disabled"
                    }
                  />
                }
              />
              <Row
                label="Neural embeddings available"
                value={
                  <StatusBadge
                    kind="custom"
                    value=""
                    tone={caps.embeddings.available ? "green" : "amber"}
                    label={
                      caps.embeddings.available
                        ? "Available"
                        : "Native fallback active"
                    }
                  />
                }
              />
              <Row
                label="sentence-transformers"
                value={
                  <StatusBadge
                    kind="custom"
                    value=""
                    tone={
                      caps.embeddings.sentence_transformers_installed
                        ? "green"
                        : "amber"
                    }
                    label={
                      caps.embeddings.sentence_transformers_installed
                        ? "Installed"
                        : "Not installed"
                    }
                  />
                }
              />
              <Row
                label="FlagEmbedding (BGE)"
                value={
                  <StatusBadge
                    kind="custom"
                    value=""
                    tone={
                      caps.embeddings.flag_embedding_installed
                        ? "green"
                        : "amber"
                    }
                    label={
                      caps.embeddings.flag_embedding_installed
                        ? "Installed"
                        : "Not installed"
                    }
                  />
                }
              />
              <Row
                label="Embedding fallback"
                value={caps.embeddings.fallback_reason || "—"}
              />
              <Row label="Embedding cache" value={caps.embeddings.cache} />
              <Row
                label="SHAP model explanations"
                value={
                  <StatusBadge
                    kind="custom"
                    value=""
                    tone={caps.shap.installed ? "green" : "amber"}
                    label={
                      caps.shap.installed
                        ? caps.shap.enabled
                          ? "Installed · enabled"
                          : "Installed · disabled"
                        : "Not installed"
                    }
                  />
                }
              />
              <Row
                label="Explanation fallback"
                value={caps.shap.fallback || "—"}
              />
              <Row
                label="Haystack"
                value={
                  <span className="text-right">
                    <StatusBadge
                      kind="custom"
                      value=""
                      tone={caps.haystack.integrated ? "green" : "amber"}
                      label={
                        caps.haystack.integrated
                          ? "Integrated"
                          : caps.haystack.installed
                            ? "Installed · not integrated"
                            : "Not installed"
                      }
                    />
                    <span className="mt-1 block text-xs font-normal text-faint">
                      {caps.haystack.reason}
                    </span>
                  </span>
                }
              />
              <Row
                label="OSSTRL"
                value={
                  <span className="text-right">
                    <StatusBadge
                      kind="custom"
                      value=""
                      tone={caps.osstrl.integrated ? "green" : "amber"}
                      label={
                        caps.osstrl.integrated
                          ? "Integrated"
                          : "Reference only"
                      }
                    />
                    <span className="mt-1 block text-xs font-normal text-faint">
                      License: {caps.osstrl.license} · {caps.osstrl.reason}
                    </span>
                  </span>
                }
              />
            </>
          ) : (
            <p className="py-4 text-sm text-faint">
              Capability report unavailable.
            </p>
          )}
        </div>
        <p className="mx-5 mb-5 rounded-xl border border-line bg-panel px-4 py-3 text-xs leading-relaxed text-muted">
          Optional packages are imported lazily in the backend. When one is
          unavailable, the pipeline records the fallback above and continues —
          nothing is downloaded or called over the network at runtime.
        </p>
      </div>

      {/* Local preferences */}
      <div className="card mt-4 overflow-hidden">
        <CardHeader
          icon={FileText}
          title="Local preferences"
          subtitle="Stored in this browser only (localStorage)"
        />
        <div className="px-5 py-4">
          <label htmlFor="default-evidence-filter" className="label">
            Default evidence status filter
          </label>
          <p className="mt-0.5 text-xs text-faint">
            Pre-selects this status when viewing the evidence table of a new result.
          </p>
          <select
            id="default-evidence-filter"
            value={defaultFilter}
            onChange={(e) => changeDefaultFilter(e.target.value)}
            className="select mt-2 max-w-xs"
          >
            <option value="">All statuses</option>
            <option value="confirmed">Confirmed</option>
            <option value="proposed">Proposed</option>
            <option value="contradicted">Contradicted</option>
            <option value="unclear">Unclear</option>
          </select>
        </div>
      </div>

      {/* Links */}
      <div className="card mt-4 p-5">
        <h2 className="mb-3 flex items-center gap-2 section-title">
          <Server className="h-4 w-4 text-primary" />
          Developer resources
        </h2>
        <div className="flex flex-wrap gap-3">
          <a
            href="/api/docs"
            target="_blank"
            rel="noreferrer"
            className="btn btn-secondary"
          >
            <ExternalLink className="h-4 w-4" />
            Open API docs (Swagger UI)
          </a>
          <a
            href="/api/redoc"
            target="_blank"
            rel="noreferrer"
            className="btn btn-secondary"
          >
            <ExternalLink className="h-4 w-4" />
            ReDoc reference
          </a>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-faint">
          In development, run the backend with{" "}
          <code className="rounded-md bg-panel px-1.5 py-0.5">
            uvicorn app.main:app --reload --port 8000
          </code>{" "}
          — the Vite dev server proxies{" "}
          <code className="rounded-md bg-panel px-1.5 py-0.5">/api</code> to it. In
          production the built frontend is served by the backend itself from the
          same origin, so links work directly.
        </p>
      </div>
    </div>
  );
}
