import { AlertTriangle, PlugZap, RefreshCw, XCircle } from "lucide-react";

interface ErrorBannerProps {
  message: string;
  networkError?: boolean;
  onRetry?: () => void;
  /** Optional extra hint rendered under the message. */
  hint?: string;
}

/** Real error message from the API (404/422/detail) or a network failure. */
export default function ErrorBanner({
  message,
  networkError = false,
  onRetry,
  hint,
}: ErrorBannerProps) {
  const Icon = networkError ? PlugZap : XCircle;
  return (
    <div
      className="flex items-start gap-3 rounded-2xl border border-rose-200/80 bg-rose-50/80 px-4 py-3.5 text-rose-900 shadow-[0_8px_24px_-20px_rgba(220,38,38,0.6)] backdrop-blur-sm"
      role="alert"
    >
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-rose-100 text-rose-600 ring-1 ring-inset ring-rose-200/70">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">
          {networkError ? "Backend not reachable" : "Something went wrong"}
        </p>
        <p className="mt-0.5 break-words text-sm text-rose-800/90">{message}</p>
        {hint && <p className="mt-1 text-xs text-rose-700/70">{hint}</p>}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-rose-300/80 bg-white/80 px-3 py-1.5 text-xs font-semibold text-rose-700 transition-colors hover:bg-white"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </button>
      )}
    </div>
  );
}

interface WarningBannerProps {
  title?: string;
  message: string;
}

/** Amber informational banner (warnings from extraction / prediction). */
export function WarningBanner({ title, message }: WarningBannerProps) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-3.5 text-amber-900 shadow-[0_8px_24px_-20px_rgba(217,119,6,0.6)] backdrop-blur-sm">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-600 ring-1 ring-inset ring-amber-200/70">
        <AlertTriangle className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        {title && <p className="text-sm font-semibold">{title}</p>}
        <p className="text-sm leading-relaxed text-amber-800/90">{message}</p>
      </div>
    </div>
  );
}
