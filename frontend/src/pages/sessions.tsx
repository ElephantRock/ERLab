/**
 * SessionsPage — BATCH-22/TASK-02
 *
 * Pipeline runs grouped by session ID.
 *
 * Migrated to useResource + DataView (Phase 3, Tier 3). Two resources:
 *
 *   1. Session list — primary visible surface (loading/error/empty/ready).
 *      useResource + DataView, keyed on a stable key.
 *   2. Runs for selected session — dependent resource keyed on
 *      selectedSession, enabled when a session is clicked. Also a visible
 *      content surface (the right panel shows runs), so useResource +
 *      DataView with its own stem to avoid testid collisions with the
 *      session list (Tier 3.5 page-owned testId rule).
 *
 * The previous hand-rolled state (sessions + runs + 4 loading/error
 * flags + unguarded useEffect) is replaced by two resources. Unmount-
 * safety is inherited from react-query (was absent — latent
 * setState-after-unmount bug on navigation).
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSessionList } from "@/api/sessions";
import { listRuns } from "@/api/pipeline";
import type { PipelineRunSummary, SessionListResponse } from "@/api/types";
import { Card, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataView } from "@/components/ui/data-view";
import { useResource } from "@/lib/useResource";
import { Layers, ChevronRight } from "lucide-react";

export default function SessionsPage() {
  const navigate = useNavigate();
  const [selectedSession, setSelectedSession] = useState<string | null>(null);

  // ── Session list (primary surface) ─────────────────────────────
  const sessionsResource = useResource<SessionListResponse>(
    ["sessions", "list"],
    () => getSessionList(),
    { isEmpty: (d) => d.sessions.length === 0 },
  );

  // ── Runs for selected session (dependent surface) ──────────────
  // Keyed on selectedSession; fires only when a session is clicked.
  // Uses a distinct stem ("session-runs") to avoid testid collisions
  // with the session list's "sessions-*" stem (Tier 3.5).
  const runsResource = useResource<{ runs: PipelineRunSummary[]; total: number }>(
    ["sessions", "runs", selectedSession],
    () => listRuns({ session_id: selectedSession!, limit: 50 }),
    {
      enabled: !!selectedSession,
      isEmpty: (d) => d.runs.length === 0,
    },
  );

  // The list of runs for display — only populated when ready/empty.
  const runs: PipelineRunSummary[] =
    runsResource.status === "ready" || runsResource.status === "empty"
      ? runsResource.data.runs
      : [];

  function formatDate(dateStr: string) {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }

  return (
    <div className="space-y-6" data-testid="sessions-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Sessions</h1>
        <p className="text-muted-foreground">Pipeline runs grouped by session ID.</p>
      </div>

      {/* Session list owns the page-level loading/error/empty states.
          When the list is empty, there's nothing else to show, so the
          DataView empty state IS the page. When ready, the grid renders. */}
      <DataView
        resource={sessionsResource}
        testId="sessions"
        loading={{ lines: 4 }}
        error={{ message: "Error loading sessions" }}
        empty={{
          icon: Layers,
          title: "No sessions yet",
          message: "Start a pipeline run with a session ID to see grouped results here.",
        }}
      >
        {(data) => (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Session List */}
            <div className="lg:col-span-1 space-y-3">
              {data.sessions.map((session) => (
                <Card
                  key={session.session_id}
                  className={`cursor-pointer hover:bg-accent/50 transition-colors ${
                    selectedSession === session.session_id ? "ring-2 ring-primary" : ""
                  }`}
                  onClick={() => setSelectedSession(session.session_id)}
                  data-testid={`session-card-${session.session_id}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate" data-testid={`session-name-${session.session_id}`}>
                          {session.session_id}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="secondary" data-testid={`session-count-${session.session_id}`}>
                            {session.run_count} run{session.run_count !== 1 ? "s" : ""}
                          </Badge>
                          <span className="text-xs text-muted-foreground" data-testid={`session-date-${session.session_id}`}>
                            {formatDate(session.latest_run_at)}
                          </span>
                        </div>
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {/* Run List for Selected Session */}
            <div className="lg:col-span-2">
              {selectedSession ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <CardTitle>{selectedSession}</CardTitle>
                    <Badge variant="outline">{runs.length} run{runs.length !== 1 ? "s" : ""}</Badge>
                  </div>

                  <DataView
                    resource={runsResource}
                    testId="session-runs"
                    loading={{ lines: 3 }}
                    error={{ message: "Failed to load runs" }}
                    empty={{
                      what: "runs",
                      message: "This session has no runs.",
                    }}
                  >
                    {(runData) => (
                      <div className="space-y-3" data-testid="sessions-runs-list">
                        {runData.runs.map((run) => (
                          <Card
                            key={run.id}
                            className="cursor-pointer hover:bg-accent/50 transition-colors"
                            onClick={() => navigate(`/runs/${run.id}`)}
                            data-testid={`session-run-${run.id}`}
                          >
                            <CardContent className="p-4">
                              <div className="flex items-center justify-between">
                                <div>
                                  <p className="text-sm font-medium">Run #{run.id}</p>
                                  <p className="text-xs text-muted-foreground">{run.domain}</p>
                                </div>
                                <div className="flex items-center gap-2">
                                  <Badge
                                    className={
                                      run.status === "completed"
                                        ? "bg-success/10 text-success"
                                        : run.status === "failed"
                                        ? "bg-destructive/10 text-destructive"
                                        : run.status === "running"
                                        ? "bg-info/10 text-info"
                                        : "bg-muted/50 text-muted-foreground"
                                    }
                                  >
                                    {run.status}
                                  </Badge>
                                  {run.ideas_count > 0 && (
                                    <Badge variant="secondary">{run.ideas_count} ideas</Badge>
                                  )}
                                  <span className="text-xs text-muted-foreground">
                                    {formatDate(run.created_at)}
                                  </span>
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    )}
                  </DataView>
                </div>
              ) : (
                <div className="flex items-center justify-center min-h-[40vh] text-muted-foreground">
                  <p>Select a session to view its runs</p>
                </div>
              )}
            </div>
          </div>
        )}
      </DataView>
    </div>
  );
}
