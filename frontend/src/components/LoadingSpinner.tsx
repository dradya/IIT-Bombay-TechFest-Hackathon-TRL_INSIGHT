interface LoadingSpinnerProps {
  label?: string;
  size?: "sm" | "md" | "lg";
}

const sizes = {
  sm: "h-4 w-4 border-2",
  md: "h-6 w-6 border-2",
  lg: "h-10 w-10 border-[3px]",
};

export default function LoadingSpinner({
  label = "Loading…",
  size = "md",
}: LoadingSpinnerProps) {
  return (
    <div className="flex items-center gap-3 text-muted" role="status">
      <span
        className={`${sizes[size]} inline-block animate-spin rounded-full border-slate-200 border-t-primary shadow-[0_0_10px_rgba(13,148,136,0.25)]`}
        aria-hidden="true"
      />
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}
