import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import { ToastProvider } from "./components/Toast";
import LoadingSpinner from "./components/LoadingSpinner";
import Overview from "./pages/Overview";

// Route-level code splitting: only the landing page ships in the first chunk.
const NewAssessment = lazy(() => import("./pages/NewAssessment"));
const AssessmentDetail = lazy(() => import("./pages/AssessmentDetail"));
const History = lazy(() => import("./pages/History"));
const Explorer = lazy(() => import("./pages/Explorer"));
const TrlGuide = lazy(() => import("./pages/TrlGuide"));
const ModelPerformance = lazy(() => import("./pages/ModelPerformance"));
const Settings = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Suspense
          fallback={
            <div className="flex min-h-[50vh] items-center justify-center">
              <LoadingSpinner label="Loading page…" />
            </div>
          }
        >
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Overview />} />
              <Route path="/new" element={<NewAssessment />} />
              <Route path="/assessments/:id" element={<AssessmentDetail />} />
              <Route path="/history" element={<History />} />
              <Route path="/explorer" element={<Explorer />} />
              <Route path="/trl-guide" element={<TrlGuide />} />
              <Route path="/model-performance" element={<ModelPerformance />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ToastProvider>
  );
}
