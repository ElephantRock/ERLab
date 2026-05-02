import { Routes, Route, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/app-shell";
import DashboardPage from "./pages/dashboard";
import PipelineNewPage from "./pages/pipeline-new";
import RunDetailPage from "./pages/run-detail";
import IdeasBrowserPage from "./pages/ideas-browser";
import IdeaDetailPage from "./pages/idea-detail";
import GapsExplorerPage from "./pages/gaps-explorer";
import KnowledgeSearchPage from "./pages/knowledge-search";
import SettingsPage from "./pages/settings";
import Placeholder from "./pages/placeholder";
import CostsPage from "./pages/costs";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/pipeline/new" element={<PipelineNewPage />} />
        <Route path="/runs/:id" element={<RunDetailPage />} />
        <Route path="/ideas" element={<IdeasBrowserPage />} />
        <Route path="/ideas/:id" element={<IdeaDetailPage />} />
        <Route path="/gaps" element={<GapsExplorerPage />} />
        <Route path="/knowledge" element={<KnowledgeSearchPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/costs" element={<CostsPage />} />
        <Route path="/memory" element={<Placeholder title="Memory" />} />
        <Route path="/governance" element={<Placeholder title="Governance" />} />
        <Route path="/traces" element={<Placeholder title="Traces" />} />
        <Route path="/sessions" element={<Placeholder title="Sessions" />} />
        <Route path="/literature" element={<Placeholder title="Literature" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
