/* Local (localStorage) user preferences — single source of truth so the
   Settings page and the components that consume a preference can never
   drift apart. All access is guarded: storage can be unavailable in
   private mode / blocked contexts. */

export const PREF_DEFAULT_EVIDENCE_FILTER = "trl_insight.default_evidence_filter";

const EVIDENCE_STATUSES = new Set([
  "",
  "confirmed",
  "proposed",
  "contradicted",
  "unclear",
]);

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable — the preference simply won't persist */
  }
}

/** Default status filter pre-selected in the evidence table ("" = all). */
export function readDefaultEvidenceFilter(): string {
  const raw = safeGet(PREF_DEFAULT_EVIDENCE_FILTER);
  if (raw !== null && EVIDENCE_STATUSES.has(raw)) return raw;
  return "";
}

export function writeDefaultEvidenceFilter(value: string): void {
  safeSet(PREF_DEFAULT_EVIDENCE_FILTER, value);
}
