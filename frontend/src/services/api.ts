/* Small typed fetch wrapper for the TRL INSIGHT API.
   No axios — plain fetch with a typed ApiError. */

import type {
  AnalyzeRequest,
  AssessmentListResponse,
  AssessmentResult,
  AssessmentTimeline,
  CapabilitiesResponse,
  CompareResponse,
  ContradictionReport,
  DocumentInfo,
  DocumentSummary,
  DocumentUploadResponse,
  KnowledgeGraph,
  Questionnaire,
  ReassessRequest,
  ReviewCreate,
  ReviewListResponse,
  ReviewModel,
  TechnologyRoadmap,
} from "../types";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, detail: string, code = "error") {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Extract a human readable message from any thrown value. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return String(err);
}

/** True when the failure looks like the backend being down / unreachable. */
export function isNetworkError(err: unknown): boolean {
  if (err instanceof ApiError) return err.status === 0;
  return err instanceof TypeError;
}

/** Shown whenever the API cannot be reached. Worded so it stays correct in
    single-server mode (backend and SPA on the same origin) as well as in dev. */
const UNREACHABLE_MESSAGE =
  "The API server is not responding. If you are running locally, make sure " +
  "the backend is up (default: http://127.0.0.1:8000).";

const TIMEOUT_MESSAGE = "The request timed out. Please try again.";

/** fetch with a timeout; resolves to the Response or rethrows. */
async function fetchWithTimeout(
  input: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  return await fetch(input, { ...init, signal: AbortSignal.timeout(timeoutMs) });
}

/** Map a fetch rejection to the right ApiError (unreachable vs timeout). */
function toNetworkError(err: unknown): ApiError {
  if (err instanceof DOMException && err.name === "TimeoutError") {
    return new ApiError(0, TIMEOUT_MESSAGE, "timeout");
  }
  if (err instanceof Error && err.name === "TimeoutError") {
    return new ApiError(0, TIMEOUT_MESSAGE, "timeout");
  }
  return new ApiError(0, UNREACHABLE_MESSAGE, "network_error");
}

async function parseError(res: Response): Promise<ApiError> {
  let detail = `Request failed with status ${res.status}`;
  let code = "error";
  let parsed = false;
  try {
    const body = await res.json();
    parsed = true;
    if (body && typeof body === "object") {
      const d = (body as { detail?: unknown }).detail;
      const c = (body as { code?: unknown }).code;
      if (typeof d === "string") detail = d;
      else if (Array.isArray(d)) detail = d.map(String).join("; ");
      else if (d && typeof d === "object" && "detail" in d) {
        const inner = (d as { detail?: unknown }).detail;
        if (typeof inner === "string") detail = inner;
      } else if (d !== undefined) detail = JSON.stringify(d);
      if (typeof c === "string") code = c;
    }
  } catch {
    /* non-JSON error body — keep the default message */
  }
  // The dev proxy answers with a non-JSON 500 when the backend is down;
  // treat that (and plain 502/503/504 gateways) as an unreachable backend.
  if (!parsed && (res.status === 500 || res.status === 502 || res.status === 503 || res.status === 504)) {
    return new ApiError(0, UNREACHABLE_MESSAGE, "network_error");
  }
  return new ApiError(res.status, detail, code);
}

async function request<T>(
  path: string,
  init: RequestInit,
  timeoutMs = 20000,
): Promise<T> {
  let res: Response;
  try {
    res = await fetchWithTimeout(path, init, timeoutMs);
  } catch (err) {
    throw toNetworkError(err);
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  // Guard against a 200 with a non-JSON body (e.g. a misconfigured proxy
  // answering with HTML) so users never see a raw parser error.
  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new ApiError(
      res.status,
      `Expected a JSON response but received "${contentType || "unknown"}".`,
      "unexpected_content",
    );
  }
  return (await res.json()) as T;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export function apiPost<T>(
  path: string,
  body: unknown,
  timeoutMs = 60000,
): Promise<T> {
  return request<T>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    timeoutMs,
  );
}

export function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

export function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return request<T>(path, { method: "POST", body: form }, 120000);
}

/** Filename from a Content-Disposition header (RFC 5987 / plain). */
function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      /* fall through */
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  if (plain) return plain[1].trim();
  return fallback;
}

function triggerDownload(blob: Blob, filename: string): void {
  if (blob.size === 0) {
    throw new ApiError(
      0,
      "The server returned an empty file. Please regenerate the report.",
      "empty_file",
    );
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Never revoke synchronously: the browser reads the blob asynchronously
  // after the click, and revoking early can cancel the download or save an
  // empty file (the classic "PDF won't download" bug).
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/* ---------------------------------------------------------------------------
   Typed endpoint helpers (thin, no hidden behaviour).
   --------------------------------------------------------------------------- */

export function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  return apiUpload<DocumentUploadResponse>("/api/documents/upload", file);
}

export function listDocuments(): Promise<DocumentInfo[]> {
  return apiGet<DocumentInfo[]>("/api/documents");
}

export function analyzeDocuments(body: AnalyzeRequest): Promise<AssessmentResult> {
  return apiPost<AssessmentResult>("/api/assessments/analyze", body);
}

export function listAssessments(
  params: Record<string, string | number | boolean | undefined> = {},
): Promise<AssessmentListResponse> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<AssessmentListResponse>(`/api/assessments${suffix}`);
}

export function getCapabilities(): Promise<CapabilitiesResponse> {
  return apiGet<CapabilitiesResponse>("/api/system/capabilities");
}

export function getDocumentSummary(assessmentId: string): Promise<DocumentSummary[]> {
  return apiGet<DocumentSummary[]>(`/api/assessments/${assessmentId}/documents`);
}

export function getKnowledgeGraph(assessmentId: string): Promise<KnowledgeGraph> {
  return apiGet<KnowledgeGraph>(`/api/assessments/${assessmentId}/graph`);
}

export function getContradictions(assessmentId: string): Promise<ContradictionReport> {
  return apiGet<ContradictionReport>(`/api/assessments/${assessmentId}/contradictions`);
}

export function getRoadmap(assessmentId: string): Promise<TechnologyRoadmap> {
  return apiGet<TechnologyRoadmap>(`/api/assessments/${assessmentId}/roadmap`);
}

export function getQuestionnaire(assessmentId: string): Promise<Questionnaire> {
  return apiGet<Questionnaire>(`/api/assessments/${assessmentId}/questionnaire`);
}

export function getTimeline(assessmentId: string): Promise<AssessmentTimeline> {
  return apiGet<AssessmentTimeline>(`/api/assessments/${assessmentId}/timeline`);
}

export function listReviews(assessmentId: string): Promise<ReviewListResponse> {
  return apiGet<ReviewListResponse>(`/api/assessments/${assessmentId}/reviews`);
}

export function createReview(
  assessmentId: string,
  body: ReviewCreate,
): Promise<ReviewModel> {
  return apiPost<ReviewModel>(`/api/assessments/${assessmentId}/reviews`, body);
}

export function reassess(
  assessmentId: string,
  body: ReassessRequest,
): Promise<AssessmentResult> {
  return apiPost<AssessmentResult>(
    `/api/assessments/${assessmentId}/reassess`,
    body,
    120000,
  );
}

export function compareAssessments(ids: string[]): Promise<CompareResponse> {
  return apiGet<CompareResponse>(
    `/api/assessments/compare?ids=${encodeURIComponent(ids.join(","))}`,
  );
}

/** GET a file (PDF / JSON attachment) and save it via a blob download. */
export async function downloadFile(
  path: string,
  fallbackName: string,
): Promise<void> {
  let res: Response;
  try {
    res = await fetchWithTimeout(path, { method: "GET" }, 60000);
  } catch (err) {
    throw toNetworkError(err);
  }
  if (!res.ok) throw await parseError(res);
  const blob = await res.blob();
  const name = filenameFromDisposition(
    res.headers.get("Content-Disposition"),
    fallbackName,
  );
  triggerDownload(blob, name);
}
