import type { ReactNode } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";

export interface FilterField {
  key: string;
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}

interface FilterBarProps {
  searchValue: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  /** Set false for pages that only need dropdown/date filters. */
  showSearch?: boolean;
  fields?: FilterField[];
  /** Extra controls (e.g. date range inputs) rendered inline. */
  extra?: ReactNode;
  onClear: () => void;
  hasActiveFilters: boolean;
}

/** Consistent filter row: debounced text search + selects + clear. */
export default function FilterBar({
  searchValue,
  onSearchChange,
  searchPlaceholder = "Search…",
  showSearch = true,
  fields = [],
  extra,
  onClear,
  hasActiveFilters,
}: FilterBarProps) {
  return (
    <div className="card flex flex-wrap items-end gap-3 p-4">
      {showSearch && (
        <div className="min-w-56 flex-1">
          <label htmlFor="filter-search" className="label">
            <span className="inline-flex items-center gap-1.5">
              <SlidersHorizontal className="h-3 w-3 text-faint" />
              Search
            </span>
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              id="filter-search"
              type="search"
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full rounded-lg border border-line-strong bg-white py-2 pl-9 pr-3 text-sm text-ink"
            />
          </div>
        </div>
      )}
      {fields.map((f) => (
        <div key={f.key} className="min-w-40">
          <label htmlFor={`filter-${f.key}`} className="label">
            {f.label}
          </label>
          <select
            id={`filter-${f.key}`}
            value={f.value}
            onChange={(e) => f.onChange(e.target.value)}
            className="w-full rounded-lg border border-line-strong bg-white px-3 py-2 text-sm text-ink"
          >
            <option value="">All</option>
            {f.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      ))}
      {extra}
      {hasActiveFilters && (
        <button type="button" onClick={onClear} className="btn btn-secondary">
          <X className="h-4 w-4" />
          Clear
        </button>
      )}
    </div>
  );
}
