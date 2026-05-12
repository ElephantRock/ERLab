import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getSessionList } from "@/api/sessions";
import { listRuns } from "@/api/pipeline";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SessionGroup, PipelineRunSummary } from "@/api/types";
import { Layers, Loader2, AlertCircle, ChevronRight } from "lucide-react";

export default function SessionsPage() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<SessionGroup[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [runs, setRuns] = useState<PipelineRunSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunsLoading, setIsRunsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getSessionList();
        setSessions(data.sessions);
      } catch (err) {
        setError("Failed to load sessions");
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  async function handleSelectSession(sessionId: string) {
    setSelectedSession(sessionId);
    setIsRunsLoading(true);
    try {
      const data = await listRuns({ session_id: sessionId, limit: 50 });
      setRuns(data.runs);
    } catch (err) {
      setError("Failed to load runs");
    } finally {
      setIsRunsLoading(false);
    }
  }

  function formatDate(dateStr: string) {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="sessions-loading">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">Loading sessions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="sessions-error">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-destructive font-medium">Error loading sessions</p>
        <p className="text-muted-foreground text-sm">{error}</p>
      </div>
    );
  }

  if (sessions.length === 0 && !selectedSession) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4" data-testid="sessions-empty">
        <Layers className="h-12 w-12 text-muted-foreground" />
        <h1 className="text-2xl font-bold tracking-tight">Sessions</h1>
        <p className="text-muted-foreground">No sessions yet. Start a pipeline run with a session ID to see grouped results here.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="sessions-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Sessions</h1>
        <p className="text-muted-foreground">Pipeline runs grouped by session ID.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Session List */}
        <div className="lg:col-span-1 space-y-3">
          {sessions.map((session) => (
            <Card
              key={session.session_id}
              className={`cursor-pointer hover:bg-accent/50 transition-colors ${
                selectedSession === session.session_id ? "ring-2 ring-primary" : ""
              }`}
              onClick={() => handleSelectSession(session.session_id)}
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

              {isRunsLoading ? (
                <div className="flex items-center gap-2 p-4" data-testid="sessions-runs-loading">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="text-sm text-muted-foreground">Loading runs...</span>
                </div>
              ) : (
                <div className="space-y-3" data-testid="sessions-runs-list">
                  {runs.map((run) => (
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
            </div>
          ) : (
            <div className="flex items-center justify-center min-h-[40vh] text-muted-foreground">
              <p>Select a session to view its runs</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
