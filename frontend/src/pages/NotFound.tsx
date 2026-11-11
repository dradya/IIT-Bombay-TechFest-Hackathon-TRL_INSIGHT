import { ArrowLeft, Compass } from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "../components/PageHeader";

export default function NotFound() {
  return (
    <div>
      <PageHeader
        title="Page not found"
        subtitle="That route does not exist in TRL INSIGHT."
      />
      <div className="card relative overflow-hidden px-6 py-16 text-center">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(13,148,136,0.08),transparent_60%)]" />
        <div className="relative flex flex-col items-center">
          <span className="icon-tile mb-4 h-14 w-14 rounded-2xl">
            <Compass className="h-6 w-6" />
          </span>
          <p className="stat-value text-5xl font-bold tracking-tight text-ink">
            404
          </p>
          <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted">
            Check the URL or head back to the overview to continue exploring your
            assessments.
          </p>
          <Link to="/" className="btn btn-primary mt-6">
            <ArrowLeft className="h-4 w-4" />
            Go to Overview
          </Link>
        </div>
      </div>
    </div>
  );
}
