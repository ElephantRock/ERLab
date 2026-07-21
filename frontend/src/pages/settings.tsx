import { useState, useEffect, useCallback, useRef } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useSettings } from "@/contexts/settings-context";
import { useAuth } from "@/contexts/auth-context";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ModelStatusPanel } from "@/components/settings/model-status-panel";
import { StageModelEditor } from "@/components/settings/stage-model-editor";
import { testConnection, getDetailedStatus, type DetailedStatus } from "@/api/client";
import { getEvolutionStatus, type EvolutionStatus } from "@/api/autonomous";
import { listUsers, type AuthUser } from "@/api/auth";
import { RoleBadge } from "@/components/auth/role-badge";
import {
  Server,
  Settings2,
  Palette,
  HelpCircle,
  FlaskConical,
  Users,
  ChevronDown,
  ChevronRight,
  Activity,
} from "lucide-react";

type ConnectionState = "idle" | "testing" | "connected" | "error";

/** Section header with icon + collapsible state for Advanced. */
function SectionHeader({
  icon: Icon,
  title,
  action,
}: {
  icon: React.ElementType;
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <h2 className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
      {action && <div className="ml-auto">{action}</div>}
    </div>
  );
}

/** Model status panel with its own query client. */
function SettingsModelSection() {
  const queryClientRef = useRef<QueryClient>();
  if (!queryClientRef.current) {
    queryClientRef.current = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 30000 } },
    });
  }
  return (
    <QueryClientProvider client={queryClientRef.current}>
      <ModelStatusPanel />
      <div className="mt-4">
        <StageModelEditor />
      </div>
    </QueryClientProvider>
  );
}

export default function Settings() {
  const { apiUrl, apiKey, theme, setApiUrl, setApiKey, setTheme } = useSettings();

  // ── Connection state ────────────────────────────────────────────
  const [connState, setConnState] = useState<ConnectionState>("idle");
  const [connError, setConnError] = useState<string>("");
  const [connLatency, setConnLatency] = useState<number | null>(null);
  const [connVersion, setConnVersion] = useState<string>("");

  // ── Backend info ────────────────────────────────────────────────
  const [detailedStatus, setDetailedStatus] = useState<DetailedStatus | null>(null);

  // ── Evolution (read-only) ───────────────────────────────────────
  const [evolutionStatus, setEvolutionStatus] = useState<EvolutionStatus | null>(null);

  // ── User management ─────────────────────────────────────────────
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AuthUser[]>([]);

  // ── Defaults ────────────────────────────────────────────────────
  const [defaultDomain, setDefaultDomain] = useState(() => {
    return localStorage.getItem("erock_default_domain") || "";
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // ── Auto-test connection on mount ──────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function autoTest() {
      setConnState("testing");
      const start = performance.now();
      const result = await testConnection(apiUrl || undefined);
      const latency = performance.now() - start;
      if (cancelled) return;

      setConnLatency(Math.round(latency));
      if (result.ok) {
        setConnState("connected");
        setConnVersion(result.ok ? result.version : "");
      } else {
        setConnState("error");
        setConnError(result.ok ? "" : result.error);
      }
    }

    autoTest();

    // Fetch detailed status + evolution in parallel
    getDetailedStatus()
      .then((data) => !cancelled && setDetailedStatus(data))
      .catch(() => {});

    getEvolutionStatus()
      .then((data) => !cancelled && setEvolutionStatus(data))
      .catch(() => {});

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch users on mount if admin
  useEffect(() => {
    if (currentUser?.role === "admin") {
      listUsers()
        .then((data) => setUsers(data))
        .catch(() => {});
    }
  }, [currentUser?.role]);

  const handleTestConnection = useCallback(async () => {
    setConnState("testing");
    setConnError("");
    const start = performance.now();
    const result = await testConnection(apiUrl || undefined);
    const latency = performance.now() - start;
    setConnLatency(Math.round(latency));
    if (result.ok) {
      setConnState("connected");
      setConnVersion(result.version);
    } else {
      setConnState("error");
      setConnError(result.error);
    }
  }, [apiUrl]);

  const handleDefaultDomainChange = useCallback((value: string) => {
    setDefaultDomain(value);
    localStorage.setItem("erock_default_domain", value);
  }, []);

  /** Status dot color based on connection state. */
  const dotColor =
    connState === "connected"
      ? "bg-success"
      : connState === "error"
        ? "bg-destructive"
        : connState === "testing"
          ? "bg-warning animate-pulse"
          : "bg-muted-foreground";

  return (
    <div className="space-y-5 animate-fade-in" data-testid="settings-page">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Settings2 className="h-5 w-5 text-accent" />
          <h1 className="text-2xl font-display font-semibold tracking-tight">Settings</h1>
        </div>
        <p className="text-sm text-muted-foreground">Configure your workspace, models, and preferences.</p>
      </div>

      {/* ── Connection ───────────────────────────────────────────── */}
      <Card className="card-shadow">
        <CardHeader>
          <SectionHeader icon={Server} title="API Connection" />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">API Base URL</label>
            <Input
              placeholder="http://localhost:8000"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to use the Vite proxy (defaults to localhost:8000 in dev).
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">API Key</label>
            <Input
              type="password"
              placeholder="Optional API key"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>

          {/* Connection health */}
          <div className="flex items-center gap-3">
            <Button
              onClick={handleTestConnection}
              disabled={connState === "testing"}
              variant="outline"
              data-testid="test-connection-btn"
            >
              {connState === "testing" ? "Testing..." : "Test Connection"}
            </Button>
            <span
              className={`inline-block h-3 w-3 rounded-full ${dotColor}`}
              data-testid="connection-dot"
              role="status"
              aria-label={
                connState === "connected"
                  ? "Connected"
                  : connState === "error"
                    ? "Connection error"
                    : "Not tested"
              }
            />
            {connState === "connected" && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-success" data-testid="connection-success">
                  Connected
                </span>
                {connLatency !== null && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Activity className="h-3 w-3" />
                    {connLatency}ms
                  </span>
                )}
              </div>
            )}
            {connState === "error" && (
              <span className="text-sm text-destructive" data-testid="connection-error">
                {connError}
              </span>
            )}
            {connState === "testing" && (
              <span className="text-sm text-muted-foreground" data-testid="connection-testing">
                Checking...
              </span>
            )}
          </div>

          {/* Backend info inline with connection */}
          <Separator />
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-xs text-muted-foreground block">Version</span>
              <span className="font-medium" data-testid="backend-version">
                {detailedStatus?.version ?? connVersion ?? "—"}
              </span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block">Provider</span>
              <span className="font-medium" data-testid="backend-provider">
                {detailedStatus?.provider ?? "—"}
              </span>
            </div>
            <div>
              <span className="text-xs text-muted-foreground block">Database</span>
              <span className="font-medium" data-testid="backend-db-status">
                {detailedStatus?.db_status ?? "—"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Models ───────────────────────────────────────────────── */}
      <div data-testid="models-section">
        <SettingsModelSection />
      </div>

      {/* ── Defaults ─────────────────────────────────────────────── */}
      <Card className="card-shadow">
        <CardHeader>
          <SectionHeader icon={Settings2} title="Defaults" />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Default Research Domain</label>
            <Input
              placeholder="AI, NLP, machine learning..."
              value={defaultDomain}
              onChange={(e) => handleDefaultDomainChange(e.target.value)}
              data-testid="default-domain-input"
            />
            <p className="text-xs text-muted-foreground">
              Pre-fills the domain field in new pipeline runs. Saved in your browser.
            </p>
          </div>

          <Separator />

          {/* Session info (read-only from localStorage) */}
          <div className="space-y-2">
            <label className="text-sm font-medium">Current Session</label>
            <div className="flex items-center gap-2">
              <Input
                readOnly
                aria-label="Current session ID"
                value={localStorage.getItem("erock_session_id") || "(none)"}
                className="text-muted-foreground"
                data-testid="current-session"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Set during pipeline creation. Used to group related runs.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* ── Appearance ───────────────────────────────────────────── */}
      <Card className="card-shadow">
        <CardHeader>
          <SectionHeader icon={Palette} title="Appearance" />
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2">
            <Button
              variant={theme === "light" ? "default" : "outline"}
              onClick={() => setTheme("light")}
            >
              Light
            </Button>
            <Button
              variant={theme === "dark" ? "default" : "outline"}
              onClick={() => setTheme("dark")}
            >
              Dark
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── Advanced (collapsible) ──────────────────────────────── */}
      <Card className="card-shadow">
        <CardHeader>
          <button
            className="flex items-center gap-2 w-full text-left"
            onClick={() => setAdvancedOpen(!advancedOpen)}
            aria-expanded={advancedOpen}
            data-testid="advanced-toggle"
          >
            {advancedOpen ? (
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
            )}
            <FlaskConical className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">Advanced</h2>
          </button>
        </CardHeader>
        {advancedOpen && (
          <CardContent className="space-y-6">
            {/* Self-Improvement — READ-ONLY */}
            <div data-testid="self-improve-section">
              <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Activity className="h-4 w-4 text-muted-foreground" />
                Self-Improvement
              </h3>
              <div className="space-y-2 text-sm pl-6">
                <div className="flex items-center gap-2">
                  <span className="font-medium">Evolution:</span>
                  <span data-testid="evolution-enabled-status">
                    {evolutionStatus?.enabled ? "Enabled" : "Disabled"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">Overlays Generated:</span>
                  <span data-testid="evolution-overlay-count">
                    {evolutionStatus?.overlays_generated ?? "—"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">Recent Outcomes:</span>
                  <span data-testid="evolution-outcome-count">
                    {evolutionStatus?.recent_outcomes?.length ?? 0}
                  </span>
                </div>
                {evolutionStatus?.recent_outcomes &&
                  evolutionStatus.recent_outcomes.length > 0 && (
                    <div className="mt-2 space-y-1" data-testid="evolution-outcomes-list">
                      {evolutionStatus.recent_outcomes.map((outcome, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-2 text-xs text-muted-foreground"
                        >
                          <span className="font-mono">{outcome.stage_name}</span>
                          <span>score: {outcome.score.toFixed(2)}</span>
                          <span>({outcome.run_id})</span>
                        </div>
                      ))}
                    </div>
                  )}
                <p className="text-xs text-muted-foreground mt-2">
                  Evolution parameters are managed by the system and cannot be edited.
                </p>
              </div>
            </div>

            {/* User Management (admin only) */}
            {currentUser?.role === "admin" && (
              <div data-testid="user-management-section">
                <Separator className="mb-4" />
                <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <Users className="h-4 w-4 text-muted-foreground" />
                  User Management
                </h3>
                <div className="space-y-3 pl-6">
                  {users.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No users found.</p>
                  ) : (
                    <div className="rounded-md border">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b bg-muted/50">
                            <th className="px-3 py-2 text-left font-medium">Username</th>
                            <th className="px-3 py-2 text-left font-medium">Email</th>
                            <th className="px-3 py-2 text-left font-medium">Role</th>
                          </tr>
                        </thead>
                        <tbody>
                          {users.map((u) => (
                            <tr key={u.id} className="border-b last:border-0">
                              <td className="px-3 py-2">{u.username}</td>
                              <td className="px-3 py-2">{u.email}</td>
                              <td className="px-3 py-2">
                                <RoleBadge role={u.role} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {/* ── Help ─────────────────────────────────────────────────── */}
      <Card className="card-shadow">
        <CardHeader>
          <SectionHeader icon={HelpCircle} title="Help & Onboarding" />
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-3">
            Re-show the guided introduction that appears for first-time users.
          </p>
          <Button
            variant="outline"
            onClick={() => {
              localStorage.removeItem("erock_onboarding_complete");
              window.location.href = "/";
            }}
            data-testid="show-onboarding-btn"
          >
            Show Onboarding Again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
