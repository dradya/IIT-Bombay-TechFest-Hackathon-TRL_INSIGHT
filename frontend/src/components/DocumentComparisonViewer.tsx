import { FileText } from "lucide-react";
import type { DocumentSummary } from "../types";
import { formatDate } from "../utils/format";

interface DocumentComparisonViewerProps {
  documents: DocumentSummary[];
}

const ROWS: {
  key: keyof DocumentSummary;
  label: string;
  render: (d: DocumentSummary) => string;
}[] = [
  { key: "page_count", label: "Pages", render: (d) => (d.page_count > 0 ? String(d.page_count) : "—") },
  {
    key: "char_count",
    label: "Characters",
    render: (d) => (d.char_count > 0 ? d.char_count.toLocaleString() : "—"),
  },
  { key: "extraction_method", label: "Extraction", render: (d) => d.extraction_method || "—" },
  { key: "evidence_count", label: "Evidence", render: (d) => String(d.evidence_count) },
  { key: "confirmed", label: "Confirmed", render: (d) => String(d.confirmed) },
  { key: "proposed", label: "Proposed", render: (d) => String(d.proposed) },
  { key: "unclear", label: "Unclear", render: (d) => String(d.unclear) },
  { key: "contradicted", label: "Contradicted", render: (d) => String(d.contradicted) },
  { key: "duplicates", label: "Duplicate claims", render: (d) => String(d.duplicates) },
  { key: "outdated", label: "Outdated items", render: (d) => String(d.outdated) },
  {
    key: "uploaded_at",
    label: "Uploaded",
    render: (d) => (d.uploaded_at ? formatDate(d.uploaded_at) : "—"),
  },
];

/** Side-by-side provenance view for every document in the assessment. */
export default function DocumentComparisonViewer({
  documents,
}: DocumentComparisonViewerProps) {
  if (documents.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-line bg-panel/70 px-4 py-4 text-sm text-muted">
        No document provenance is stored for this assessment.
      </div>
    );
  }

  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead>
          <tr className="border-b border-line text-[11px] uppercase tracking-[0.1em] text-faint">
            <th className="sticky left-0 bg-white px-3 py-2.5 font-semibold">Metric</th>
            {documents.map((d, i) => (
              <th key={`${d.document_id ?? d.filename}-${i}`} className="px-3 py-2.5 font-semibold">
                <span className="inline-flex items-center gap-1.5 text-ink">
                  <FileText className="h-3.5 w-3.5 text-primary" />
                  <span className="max-w-44 truncate" title={d.filename}>
                    {d.filename || `Document ${i + 1}`}
                  </span>
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line/70">
          {ROWS.map((row) => (
            <tr key={row.key as string}>
              <td className="sticky left-0 bg-white px-3 py-2 text-xs font-medium text-muted">
                {row.label}
              </td>
              {documents.map((d, i) => (
                <td key={i} className="px-3 py-2 text-xs tabular-nums text-ink-soft">
                  {row.render(d)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
