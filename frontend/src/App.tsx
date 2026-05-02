import { Suspense, lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { AppShell } from "./components/layout/app-shell";
import LoginPage from "./pages/login";
import type { ReactNode } from "react";

// Lazy-loaded pages (BATCH-48)
const DashboardPage = lazy(() => import("./pages/dashboard"));
const PipelineNewPage = lazy(() => import("./pages/pipeline-new"));
const RunDetailPage = lazy(() => import("./pages/run-detail"));
const IdeasBrowserPage = lazy(() => import("./pages/ideas-browser"));
const IdeaDetailPage = lazy(() => import("./pages/idea-detail"));
const GapsExplorerPage = lazy(() => import("./pages/gaps-explorer"));
const GapDetailPage = lazy(() => import("./pages/gap-detail"));
const KnowledgeSearchPage = lazy(() => import("./pages/knowledge-search"));
const SettingsPage = lazy(() => import("./pages/settings"));
const LiteraturePage = lazy(() => import("./pages/literature"));
const MemoryBrowserPage = lazy(() => import("./pages/memory"));
const CostsPage = lazy(() => import("./pages/costs"));
const GovernancePage = lazy(() => import("./pages/governance"));
const TracesPage = lazy(() => import("./pages/traces"));
const SessionsPage = lazy(() => import("./pages/sessions"));
const KnowledgeGraphPage = lazy(() => import("./pages/knowledge-graph"));
const AutonomousPage = lazy(() => import("./pages/autonomous"));
const PluginsPage = lazy(() => import("./pages/plugins"));

function LoadingScreen() {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}

/** Redirects to /login if not authenticated (BATCH-28). */
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <span className="text-muted-foreground">Loading...</span>
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <AppShell>
              <Suspense fallback={<LoadingScreen />}>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/pipeline/new" element={<PipelineNewPage />} />
                  <Route path="/runs/:id" element={<RunDetailPage />} />
                  <Route path="/ideas" element={<IdeasBrowserPage />} />
                  <Route path="/ideas/:id" element={<IdeaDetailPage />} />
                  <Route path="/gaps" element={<GapsExplorerPage />} />
                  <Route path="/gaps/:id" element={<GapDetailPage />} />
                  <Route path="/knowledge" element={<KnowledgeSearchPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/costs" element={<CostsPage />} />
                  <Route path="/memory" element={<MemoryBrowserPage />} />
                  <Route path="/governance" element={<GovernancePage />} />
                  <Route path="/traces" element={<TracesPage />} />
                  <Route path="/sessions" element={<SessionsPage />} />
                  <Route path="/literature" element={<LiteraturePage />} />
                  <Route path="/knowledge-graph" element={<KnowledgeGraphPage />} />
                  <Route path="/autonomous" element={<AutonomousPage />} />
                  <Route path="/plugins" element={<PluginsPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Suspense>
            </AppShell>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
