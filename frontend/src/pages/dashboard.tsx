import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { listRuns } from "@/api/pipeline";
import { getSystemStatus } from "@/api/status";
import { listIdeas } from "@/api/ideas";
import { RunCard } from "@/components/pipeline/run-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useNavigate } from "react-router-dom";
import { Activity, Lightbulb, FlaskConical, Server } from "lucide-react";

const ScoreDistributionChart = lazy(() =>
  import("@/components/charts/score-distribution").then((m) => ({ default: m.ScoreDistributionChart })),
);
const DomainBreakdownChart = lazy(() =>
  import("@/components/charts/domain-breakdown").then((m) => ({ default: m.DomainBreakdownChart })),
);
const RunStatusChart = lazy(() =>
  import("@/components/charts/run-status-chart").then((m) => ({ default: m.RunStatusChart })),
);

export default function Dashboard() {
  const navigate = useNavigate();

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["status"],
    queryFn: getSystemStatus,
  });

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ["runs", { limit: 5 }],
    queryFn: () => listRuns({ limit: 5 }),
  });

  const { data: ideasData, isLoading: ideasLoading } = useQuery({
    queryKey: ["ideas", { limit: 5 }],
    queryFn: () => listIdeas({ limit: 5 }),
  });

  const { data: chartIdeas } = useQuery({
    queryKey: ["ideas", { limit: 200 }],
    queryFn: () => listIdeas({ limit: 200 }),
  });

  const { data: chartRuns } = useQuery({
    queryKey: ["runs", { limit: 50 }],
    queryFn: () => listRuns({ limit: 50 }),
  });

  const hasChartData =
    (chartIdeas?.ideas.length ?? 0) > 0 || (chartRuns?.runs.length ?? 0) > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">Overview of your research pipeline.</p>
      </div>

      <div className="dashboard-grid grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {runsLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <span className="text-2xl font-bold">{runsData?.total ?? 0}</span>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Ideas</CardTitle>
            <Lightbulb className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {ideasLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <span className="text-2xl font-bold">{ideasData?.total ?? 0}</span>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">System</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statusLoading ? (
              <Skeleton className="h-8 w-24" />
            ) : (
              <div>
                <span className="text-2xl font-bold">{status?.app_name ?? "—"}</span>
                <p className="text-xs text-muted-foreground">v{status?.version ?? "—"}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {hasChartData && (
        <Suspense fallback={<Skeleton className="h-64 w-full" />}>
          <div className="space-y-4">
            <h2 className="text-lg font-semibold">Analytics</h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Score Distribution</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScoreDistributionChart ideas={chartIdeas?.ideas ?? []} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Run Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <RunStatusChart runs={chartRuns?.runs ?? []} />
                </CardContent>
              </Card>
            </div>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Ideas by Domain</CardTitle>
              </CardHeader>
              <CardContent>
                <DomainBreakdownChart ideas={chartIdeas?.ideas ?? []} />
              </CardContent>
            </Card>
          </div>
        </Suspense>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent Runs</h2>
            <Button
              variant="default"
              size="sm"
              onClick={() => navigate("/pipeline/new")}
              data-testid="new-run-btn"
            >
              New Pipeline
            </Button>
          </div>
          {runsLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : runsData?.runs.length ? (
            runsData.runs.map((run) => (
                <RunCard key={run.id} run={run} onClick={() => navigate(`/runs/${run.id}`)} />
              ))
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                <FlaskConical className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No runs yet. Start your first pipeline!</p>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent Ideas</h2>
            <button
              onClick={() => navigate("/ideas")}
              className="text-sm text-primary hover:underline"
            >
              View all
            </button>
          </div>
          {ideasLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : ideasData?.ideas.length ? (
            ideasData.ideas.map((idea) => (
              <Card
                key={idea.id}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => navigate(`/ideas/${idea.id}`)}
              >
                <CardContent className="p-4">
                  <p className="text-sm font-medium line-clamp-1">{idea.title}</p>
                  <p className="text-xs text-muted-foreground">{idea.domain}</p>
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                <Lightbulb className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p>No ideas generated yet.</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
