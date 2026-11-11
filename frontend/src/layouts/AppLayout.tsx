import { useEffect, useMemo, useRef, useState } from "react";
import {
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  Bell,
  BookOpen,
  ChevronRight,
  ClipboardList,
  Command,
  FileUp,
  GitCompare,
  History,
  LayoutDashboard,
  Menu,
  Search,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { HealthResponse, OverviewResponse } from "../types";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { to: "/", label: "Overview", icon: LayoutDashboard },
      { to: "/new", label: "New Assessment", icon: FileUp },
      { to: "/history", label: "Assessment History", icon: History },
      { to: "/explorer", label: "Technology Explorer", icon: GitCompare },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { to: "/trl-guide", label: "TRL Reference Guide", icon: BookOpen },
      { to: "/model-performance", label: "Model Performance", icon: Activity },
    ],
  },
  {
    label: "System",
    items: [{ to: "/settings", label: "Settings", icon: Settings }],
  },
];

/** Custom TRL INSIGHT logo: luminous teal mark + wordmark + tagline. */
export function TrlLogo({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-teal-300 via-teal-500 to-cyan-600 text-[12px] font-extrabold tracking-tight text-white shadow-[0_10px_24px_-8px_rgba(13,148,136,0.85)]">
        <span className="absolute inset-0 rounded-xl ring-1 ring-inset ring-white/25" />
        TRL
      </span>
      {!compact && (
        <div className="min-w-0 leading-tight">
          <p className="truncate font-display text-[15px] font-bold tracking-tight text-white">
            TRL INSIGHT
          </p>
          <p className="truncate text-[11px] font-medium text-slate-400">
            Readiness intelligence
          </p>
        </div>
      )}
    </div>
  );
}

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-6" aria-label="Main navigation">
      {NAV_GROUPS.map((group) => (
        <div key={group.label}>
          <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            {group.label}
          </p>
          <div className="flex flex-col gap-1">
            {group.items.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                onClick={onNavigate}
                className={({ isActive }) =>
                  `group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-150 ${
                    isActive
                      ? "bg-gradient-to-r from-teal-400/20 via-cyan-400/10 to-transparent text-white shadow-[inset_0_0_0_1px_rgba(45,212,191,0.22)]"
                      : "text-slate-400 hover:bg-white/[0.06] hover:text-white"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-teal-300 shadow-[0_0_12px_rgba(45,212,191,0.9)]" />
                    )}
                    <Icon
                      className={`h-[18px] w-[18px] shrink-0 ${
                        isActive
                          ? "text-teal-300"
                          : "text-slate-500 group-hover:text-slate-300"
                      }`}
                      aria-hidden="true"
                    />
                    <span className="truncate">{label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function pageLabel(pathname: string): string {
  if (pathname.startsWith("/assessments/")) return "Assessment result";
  const match = NAV_GROUPS.flatMap((g) => g.items).find((item) =>
    item.to === "/" ? pathname === "/" : pathname.startsWith(item.to),
  );
  return match?.label ?? "Workspace";
}

interface CommandItem {
  id: string;
  label: string;
  hint: string;
  to: string;
  icon: LucideIcon;
}

/** Ctrl/Cmd+K palette: navigation plus recent assessments. */
function CommandPalette({
  open,
  onClose,
  recent,
}: {
  open: boolean;
  onClose: () => void;
  recent: OverviewResponse["recent"];
}) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const items = useMemo<CommandItem[]>(() => {
    const navigation = NAV_GROUPS.flatMap((group) =>
      group.items.map((item) => ({
        id: `nav-${item.to}`,
        label: item.label,
        hint: group.label,
        to: item.to,
        icon: item.icon,
      })),
    );
    const recentItems = recent.map((assessment) => ({
      id: `asm-${assessment.id}`,
      label: assessment.technology_name || "Untitled technology",
      hint: `TRL ${assessment.predicted_trl ?? "—"} · ${
        assessment.domain || "No domain"
      }`,
      to: `/assessments/${assessment.id}`,
      icon: ClipboardList,
    }));
    return [...navigation, ...recentItems];
  }, [recent]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((item) =>
      `${item.label} ${item.hint}`.toLowerCase().includes(q),
    );
  }, [items, query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActiveIndex(0);
    const timer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  if (!open) return null;

  const run = (item: CommandItem | undefined) => {
    if (!item) return;
    onClose();
    navigate(item.to);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[10vh] sm:pt-[14vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="absolute inset-0 animate-fade bg-slate-950/45 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-white shadow-[0_40px_90px_-30px_rgba(6,19,38,0.55)]">
        <div className="flex items-center gap-3 border-b border-line px-4 py-3">
          <Search className="h-4 w-4 shrink-0 text-faint" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveIndex((i) =>
                  filtered.length === 0 ? 0 : (i + 1) % filtered.length,
                );
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveIndex((i) =>
                  filtered.length === 0
                    ? 0
                    : (i - 1 + filtered.length) % filtered.length,
                );
              } else if (e.key === "Enter") {
                e.preventDefault();
                run(filtered[activeIndex]);
              } else if (e.key === "Escape") {
                e.preventDefault();
                onClose();
              }
            }}
            placeholder="Search pages and recent assessments…"
            aria-label="Command palette search"
            className="min-w-0 flex-1 border-0 bg-transparent text-sm text-ink outline-none placeholder:text-faint"
          />
          <kbd className="rounded-md border border-line bg-panel px-1.5 py-0.5 text-[10px] font-semibold text-faint">
            Esc
          </kbd>
        </div>

        <ul
          className="scrollbar-thin max-h-80 overflow-y-auto p-2"
          role="listbox"
          aria-label="Commands"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-6 text-center text-sm text-faint">
              No matching pages or assessments.
            </li>
          ) : (
            filtered.map((item, index) => {
              const Icon = item.icon;
              const active = index === activeIndex;
              return (
                <li key={item.id} role="option" aria-selected={active}>
                  <button
                    type="button"
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => run(item)}
                    className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors ${
                      active ? "bg-teal-50 text-primary-dark" : "text-ink-soft"
                    }`}
                  >
                    <Icon
                      className={`h-4 w-4 shrink-0 ${
                        active ? "text-primary" : "text-faint"
                      }`}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold">
                        {item.label}
                      </span>
                      <span className="block truncate text-xs text-faint">
                        {item.hint}
                      </span>
                    </span>
                    {active && (
                      <ChevronRight className="h-4 w-4 shrink-0 text-primary" />
                    )}
                  </button>
                </li>
              );
            })
          )}
        </ul>

        <div className="flex items-center justify-between border-t border-line bg-panel/60 px-4 py-2 text-[11px] text-faint">
          <span>↑ ↓ to navigate · Enter to open</span>
          <span className="inline-flex items-center gap-1">
            <Command className="h-3 w-3" />K to toggle
          </span>
        </div>
      </div>
    </div>
  );
}

/** Desktop sidebar layout; collapses to a top bar + drawer on small screens. */
export default function AppLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const health = useApi<HealthResponse>("/api/health");
  const overview = useApi<OverviewResponse>("/api/overview");

  const awaitingReview = overview.data?.reviews?.unreviewed ?? 0;
  const recentAssessments = useMemo(
    () => overview.data?.recent.slice(0, 6) ?? [],
    [overview.data],
  );

  // Global Ctrl/Cmd+K opens the command palette.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Reset scroll on navigation so deep links and result pages start at the top.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  // Drawer: move focus in when it opens, close on Escape and give focus
  // back to the menu button when it closes.
  useEffect(() => {
    if (!drawerOpen) return;
    closeButtonRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      menuButtonRef.current?.focus();
    };
  }, [drawerOpen]);

  const online = Boolean(health.data);
  const modelReady = Boolean(health.data?.model_available);
  const statusLabel = health.loading
    ? "Checking system…"
    : online
      ? modelReady
        ? "All systems operational"
        : "Rule-only mode"
      : "Backend offline";
  const statusDot = health.loading
    ? "bg-amber-400"
    : online
      ? modelReady
        ? "bg-emerald-400"
        : "bg-amber-400"
      : "bg-rose-400";
  const currentLabel = pageLabel(location.pathname);

  return (
    <div className="min-h-screen lg:flex">
      {/* Desktop sidebar */}
      <aside className="sidebar-surface sticky top-0 hidden h-screen w-[272px] shrink-0 flex-col border-r border-white/[0.06] lg:flex">
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-teal-400/15 blur-3xl" />
          <div className="absolute -bottom-24 -right-16 h-64 w-64 rounded-full bg-blue-500/15 blur-3xl" />
        </div>

        <div className="relative border-b border-white/[0.07] px-5 py-5">
          <TrlLogo />
        </div>

        <div className="relative flex-1 overflow-y-auto px-3 py-5">
          <NavLinks />
        </div>

        <div className="relative border-t border-white/[0.07] p-3">
          <NavLink
            to="/settings"
            className="group block rounded-xl border border-white/10 bg-white/[0.04] p-3 transition-colors hover:bg-white/[0.08]"
          >
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                {online && modelReady && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                )}
                <span
                  className={`relative inline-flex h-2 w-2 rounded-full ${statusDot}`}
                />
              </span>
              <span className="text-xs font-semibold text-white">
                {statusLabel}
              </span>
              <ArrowUpRight className="ml-auto h-3.5 w-3.5 text-slate-500 transition-colors group-hover:text-slate-300" />
            </div>
            <p className="mt-1.5 truncate text-[11px] text-slate-400">
              {health.data
                ? `${health.data.model_mode} · v${health.data.version}`
                : "Open settings to test the connection"}
            </p>
          </NavLink>
        </div>
      </aside>

      {/* Content column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Desktop top bar */}
        <header className="sticky top-0 z-30 hidden h-16 items-center justify-between border-b border-line/80 bg-white/80 px-8 backdrop-blur-xl lg:flex">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-faint">
              Workspace
            </span>
            <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
            <span className="font-medium text-ink">{currentLabel}</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg border border-line bg-panel px-2.5 py-1.5 text-xs font-medium text-muted transition-colors hover:border-line-strong hover:text-ink"
              aria-label="Open command palette"
            >
              <Search className="h-3.5 w-3.5 text-faint" />
              Search
              <kbd className="rounded border border-line bg-white px-1 py-0.5 text-[10px] font-semibold text-faint">
                Ctrl K
              </kbd>
            </button>

            <button
              type="button"
              onClick={() => navigate("/history?review_status=unreviewed")}
              className="relative rounded-lg border border-line bg-white p-2 text-muted transition-colors hover:border-line-strong hover:text-ink"
              title={
                awaitingReview > 0
                  ? `${awaitingReview} assessment(s) awaiting expert review`
                  : "No assessments awaiting review"
              }
              aria-label={`Expert review queue: ${awaitingReview} awaiting review`}
            >
              <Bell className="h-4 w-4" />
              {awaitingReview > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
                  {awaitingReview > 99 ? "99+" : awaitingReview}
                </span>
              )}
            </button>

            <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-panel px-2.5 py-1 text-[11px] font-medium text-muted">
              <span
                className={`h-1.5 w-1.5 rounded-full ${statusDot}`}
              />
              {health.data ? "API connected" : "API offline"}
            </span>
            {location.pathname !== "/new" && (
              <NavLink to="/new" className="btn btn-primary btn-sm">
                <Sparkles className="h-3.5 w-3.5" />
                New assessment
              </NavLink>
            )}
          </div>
        </header>

        {/* Mobile / tablet top bar */}
        <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line/80 bg-white/90 px-4 py-3 backdrop-blur-xl lg:hidden">
          <div className="sidebar-surface -m-1 rounded-xl px-3 py-2">
            <TrlLogo />
          </div>
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setDrawerOpen(true)}
            aria-label="Open navigation menu"
            aria-expanded={drawerOpen}
            className="btn btn-secondary btn-sm"
          >
            <Menu className="h-4 w-4" />
            Menu
          </button>
        </header>

        <main className="min-w-0 flex-1">
          <div
            key={location.pathname}
            className="animate-rise mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8"
          >
            <Outlet />
          </div>
        </main>
      </div>

      {/* Drawer overlay */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <div
            className="absolute inset-0 animate-fade bg-slate-950/50 backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="sidebar-surface animate-slide-in absolute left-0 top-0 flex h-full w-72 max-w-[85vw] flex-col overflow-hidden shadow-2xl">
            <div className="pointer-events-none absolute -left-20 -top-20 h-60 w-60 rounded-full bg-teal-400/15 blur-3xl" />
            <div className="relative flex items-center justify-between border-b border-white/[0.07] px-4 py-4">
              <TrlLogo />
              <button
                ref={closeButtonRef}
                type="button"
                onClick={() => setDrawerOpen(false)}
                aria-label="Close navigation menu"
                className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="relative flex-1 overflow-y-auto px-3 py-5">
              <NavLinks onNavigate={() => setDrawerOpen(false)} />
            </div>
            <div className="relative border-t border-white/[0.07] p-3">
              <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5">
                <span className={`h-2 w-2 rounded-full ${statusDot}`} />
                <span className="text-xs font-semibold text-white">
                  {statusLabel}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        recent={recentAssessments}
      />
    </div>
  );
}
