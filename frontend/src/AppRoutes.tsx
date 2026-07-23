/**
 * F1.5a: Production route registry — shared between the application and tests.
 *
 * Both App.tsx and integration tests import this same definition, ensuring
 * the test route graph is always the production route graph.
 *
 * The route declarations (path → element mapping) are frozen here. The page
 * components are lazy-loaded in production but eagerly imported in tests.
 */

import { Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { lazyRoute } from "@/lib/lazy-route";

// Lazy-loaded pages (production).
// F1.6.3: wrapped in lazyRoute() so import failures become typed
// LazyRouteError (classified category=lazy_route_error by the route
// boundary) instead of opaque chunk-load errors. The LoadedRouteWrapper
// inside lazyRoute clears the retry marker AFTER the route successfully
// mounts (V3-3).
const DashboardPage = lazyRoute(() => import("./pages/dashboard"));
const PipelineNewPage = lazyRoute(() => import("./pages/pipeline-new"));
const RunDetailPage = lazyRoute(() => import("./pages/run-detail"));
const IdeasBrowserPage = lazyRoute(() => import("./pages/ideas-browser"));
const IdeaDetailPage = lazyRoute(() => import("./pages/idea-detail"));
const GapsExplorerPage = lazyRoute(() => import("./pages/gaps-explorer"));
const GapDetailPage = lazyRoute(() => import("./pages/gap-detail"));
const KnowledgeSearchPage = lazyRoute(() => import("./pages/knowledge-search"));
const SettingsPage = lazyRoute(() => import("./pages/settings"));
const LiteraturePage = lazyRoute(() => import("./pages/literature"));
const MemoryBrowserPage = lazyRoute(() => import("./pages/memory"));
const CostsPage = lazyRoute(() => import("./pages/costs"));
const GovernancePage = lazyRoute(() => import("./pages/governance"));
const TracesPage = lazyRoute(() => import("./pages/traces"));
const SessionsPage = lazyRoute(() => import("./pages/sessions"));
const KnowledgeGraphPage = lazyRoute(() => import("./pages/knowledge-graph"));
const AutonomousPage = lazyRoute(() => import("./pages/autonomous"));
const PluginsPage = lazyRoute(() => import("./pages/plugins"));
const OpsPage = lazyRoute(() => import("./pages/ops"));

function LoadingScreen() {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  );
}

/**
 * The production route declarations. This is a function that takes
 * a set of page components so that both lazy (production) and eager
 * (test) imports can use the SAME route path mapping.
 */
export function createRoutes(pages: {
  Dashboard: React.ComponentType;
  PipelineNew: React.ComponentType;
  RunDetail: React.ComponentType;
  IdeasBrowser: React.ComponentType;
  IdeaDetail: React.ComponentType;
  GapsExplorer: React.ComponentType;
  GapDetail: React.ComponentType;
  KnowledgeSearch: React.ComponentType;
  Settings: React.ComponentType;
  Literature: React.ComponentType;
  Memory: React.ComponentType;
  Costs: React.ComponentType;
  Governance: React.ComponentType;
  Traces: React.ComponentType;
  Sessions: React.ComponentType;
  KnowledgeGraph: React.ComponentType;
  Autonomous: React.ComponentType;
  Plugins: React.ComponentType;
  Ops: React.ComponentType;
}) {
  return (
    <Routes>
      <Route path="/" element={<pages.Dashboard />} />
      <Route path="/pipeline/new" element={<pages.PipelineNew />} />
      <Route path="/runs/:id" element={<pages.RunDetail />} />
      <Route path="/ideas" element={<pages.IdeasBrowser />} />
      <Route path="/ideas/:id" element={<pages.IdeaDetail />} />
      <Route path="/gaps" element={<pages.GapsExplorer />} />
      <Route path="/gaps/:id" element={<pages.GapDetail />} />
      <Route path="/knowledge" element={<pages.KnowledgeSearch />} />
      <Route path="/settings" element={<pages.Settings />} />
      <Route path="/costs" element={<pages.Costs />} />
      <Route path="/memory" element={<pages.Memory />} />
      <Route path="/governance" element={<pages.Governance />} />
      <Route path="/traces" element={<pages.Traces />} />
      <Route path="/sessions" element={<pages.Sessions />} />
      <Route path="/literature" element={<pages.Literature />} />
      <Route path="/knowledge-graph" element={<pages.KnowledgeGraph />} />
      <Route path="/autonomous" element={<pages.Autonomous />} />
      <Route path="/plugins" element={<pages.Plugins />} />
      <Route path="/ops" element={<pages.Ops />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

/** Lazy page components (production). */
export const lazyPages = {
  Dashboard: DashboardPage,
  PipelineNew: PipelineNewPage,
  RunDetail: RunDetailPage,
  IdeasBrowser: IdeasBrowserPage,
  IdeaDetail: IdeaDetailPage,
  GapsExplorer: GapsExplorerPage,
  GapDetail: GapDetailPage,
  KnowledgeSearch: KnowledgeSearchPage,
  Settings: SettingsPage,
  Literature: LiteraturePage,
  Memory: MemoryBrowserPage,
  Costs: CostsPage,
  Governance: GovernancePage,
  Traces: TracesPage,
  Sessions: SessionsPage,
  KnowledgeGraph: KnowledgeGraphPage,
  Autonomous: AutonomousPage,
  Plugins: PluginsPage,
  Ops: OpsPage,
};

/** The inner authenticated route set — uses lazy pages (production). */
export function AuthenticatedRoutes() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      {createRoutes(lazyPages)}
    </Suspense>
  );
}

/** ProtectedRoute wrapper — used by App and tests. */
export function ProtectedRoute({ children, user, loading }: {
  children: ReactNode;
  user: unknown;
  loading: boolean;
}) {
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
