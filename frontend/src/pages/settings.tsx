import { useState, useEffect, useCallback } from "react";
import { useSettings } from "@/contexts/settings-context";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { testConnection, getDetailedStatus, type DetailedStatus } from "@/api/client";
import { getEvolutionStatus, type EvolutionStatus } from "@/api/autonomous";

type ConnectionState = "idle" | "testing" | "connected" | "error";

export default function Settings() {
  const { apiUrl, apiKey, theme, setApiUrl, setApiKey, setTheme } = useSettings();

  // Connection test state
  const [connState, setConnState] = useState<ConnectionState>("idle");
  const [connError, setConnError] = useState<string>("");

  // Version / detailed status
  const [detailedStatus, setDetailedStatus] = useState<DetailedStatus | null>(null);

  // Evolution status (READ-ONLY per HB-01)
  const [evolutionStatus, setEvolutionStatus] = useState<EvolutionStatus | null>(null);

  // Default domain
  const [defaultDomain, setDefaultDomain] = useState(() => {
    return localStorage.getItem("erock_default_domain") || "";
  });

  // Fetch version + evolution status on mount
  useEffect(() => {
    let cancelled = false;
    getDetailedStatus()
      .then((data) => {
        if (!cancelled) setDetailedStatus(data);
      })
      .catch(() => {
        // Version unavailable is non-fatal; just leave it null
      });
    getEvolutionStatus()
      .then((data) => {
        if (!cancelled) setEvolutionStatus(data);
      })
      .catch(() => {
        // Evolution unavailable is non-fatal
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleTestConnection = useCallback(async () => {
    setConnState("testing");
    setConnError("");
    const result = await testConnection(apiUrl || undefined);
    if (result.ok) {
      setConnState("connected");
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
      ? "bg-green-500"
      : connState === "error"
        ? "bg-red-500"
        : connState === "testing"
          ? "bg-yellow-500 animate-pulse"
          : "bg-gray-400";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Configure your API connection and preferences.</p>
      </div>

      {/* API Connection */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">API Connection</CardTitle>
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

          {/* Test Connection */}
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
              aria-label={
                connState === "connected"
                  ? "Connected"
                  : connState === "error"
                    ? "Connection error"
                    : "Not tested"
              }
            />
            {connState === "error" && (
              <span className="text-sm text-red-500" data-testid="connection-error">
                {connError}
              </span>
            )}
            {connState === "connected" && (
              <span className="text-sm text-green-600" data-testid="connection-success">
                Connected
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Backend Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Backend Info</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-medium">Version:</span>
              <span data-testid="backend-version">
                {detailedStatus?.version ?? "—"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="font-medium">Provider:</span>
              <span data-testid="backend-provider">
                {detailedStatus?.provider ?? "—"}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Default Domain */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Default Research Domain</label>
            <Input
              placeholder="e.g., AI/NLP, machine learning"
              value={defaultDomain}
              onChange={(e) => handleDefaultDomainChange(e.target.value)}
              data-testid="default-domain-input"
            />
            <p className="text-xs text-muted-foreground">
              Pre-fills the domain field in new pipeline runs. Saved in your browser.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Self-Improvement — READ-ONLY per HB-01 */}
      <Card data-testid="self-improve-section">
        <CardHeader>
          <CardTitle className="text-lg">Self-Improvement</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
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
            {evolutionStatus?.recent_outcomes && evolutionStatus.recent_outcomes.length > 0 && (
              <div className="mt-2 space-y-1" data-testid="evolution-outcomes-list">
                {evolutionStatus.recent_outcomes.map((outcome, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-xs text-muted-foreground">
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
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Appearance</CardTitle>
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
    </div>
  );
}
