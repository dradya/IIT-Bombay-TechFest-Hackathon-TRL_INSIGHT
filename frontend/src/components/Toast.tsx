import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { CheckCircle2, XCircle } from "lucide-react";

interface ToastItem {
  id: number;
  message: string;
  tone: "success" | "error";
}

interface ToastContextValue {
  showToast: (message: string, tone?: "success" | "error") => void;
}

const ToastContext = createContext<ToastContextValue>({ showToast: () => {} });

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = useCallback(
    (message: string, tone: "success" | "error" = "success") => {
      const id = nextId++;
      setToasts((prev) => [...prev, { id, message, tone }]);
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4200);
    },
    [],
  );

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2"
        aria-live="polite"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className="animate-rise pointer-events-auto flex items-start gap-2.5 rounded-xl border border-white/10 bg-slate-950/95 px-4 py-3 text-sm text-white shadow-2xl backdrop-blur-xl"
          >
            {t.tone === "success" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            ) : (
              <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
            )}
            <span className="leading-relaxed text-slate-100">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
