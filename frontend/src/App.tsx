import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/auth-context";
import { AppShell } from "./components/layout/app-shell";
import DashboardPage from "./pages/dashboard";
import PipelineNewPage from "./pages/pipeline-new";
import RunDetailPage from "./pages/run-detail";
import IdeasBrowserPage from "./pages/ideas-browser";
import IdeaDetailPage from "./pages/idea-detail";
import GapsExplorerPage from "./pages/gaps-explorer";
import GapDetailPage from "./pages/gap-detail";
import KnowledgeSearchPage from "./pages/knowledge-search";
import SettingsPage from "./pages/settings";
import LiteraturePage from "./pages/literature";
import MemoryBrowserPage from "./pages/memory";
import CostsPage from "./pages/costs";
import GovernancePage from "./pages/governance";
import TracesPage from "./pages/traces";
import SessionsPage from "./pages/sessions";
import KnowledgeGraphPage from "./pages/knowledge-graph";
import AutonomousPage from "./pages/autonomous";
import PluginsPage from "./pages/plugins";
import LoginPage from "./pages/login";
import type { ReactNode } from "react";

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
            </AppShell>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
