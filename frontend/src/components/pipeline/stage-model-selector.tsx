import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  model: string;
  location: string;
  type: string;
}

interface StageInfo {
  name: string;
  label: string;
  category: string;
  default_model: string;
}

interface ModelConfigResponse {
  models: ModelOption[];
  stages: StageInfo[];
  assignments: Record<string, string>;
}

interface StageModelSelectorProps {
  /** Current assignments, passed up to parent form */
  value: Record<string, string>;
  onChange: (assignments: Record<string, string>) => void;
}

const API_BASE = import.meta.env.VITE_API_URL || "";

export function StageModelSelector({ value, onChange }: StageModelSelectorProps) {
  const [config, setConfig] = useState<ModelConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const resp = await fetch(`${API_BASE}/api/v1/settings/models`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data: ModelConfigResponse = await resp.json();
        setConfig(data);
        // Initialize with saved assignments merged into value
        onChange({ ...data.assignments, ...value });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load models");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function handleStageChange(stageName: string, modelId: string) {
    const updated = { ...value };
    if (modelId === "auto" || modelId === "") {
      delete updated[stageName];
    } else {
      updated[stageName] = modelId;
    }
    onChange(updated);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/settings/models`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(value),
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.error?.message || `HTTP ${resp.status}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    try {
      await fetch(`${API_BASE}/api/v1/settings/models`, { method: "DELETE" });
      onChange({});
    } catch {
      // ignore
    }
  }

  if (loading) {
    return (
      <div className="text-sm text-muted-foreground py-2">
        Loading model configuration...
      </div>
    );
  }

  if (!config || config.models.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-2">
        No models configured. Enable LM Studio or configure a cloud API key.
      </div>
    );
  }

  const { models, stages } = config;

  // Group stages by category
  const categories = [
    { key: "thinking", label: "Thinking & Analysis", icon: "🧠" },
    { key: "generation", label: "Generation & Synthesis", icon: "✍️" },
    { key: "passthrough", label: "Data & Utility", icon: "⚙️" },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Choose which model handles each pipeline stage. Changes apply to new runs.
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReset}
            className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded border border-input"
          >
            Reset to Defaults
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="text-xs bg-primary text-primary-foreground px-3 py-1 rounded hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Config"}
          </button>
        </div>
      </div>

      {error && (
        <div className="text-xs text-destructive bg-destructive/5 dark:bg-destructive/20 px-3 py-2 rounded">
          {error}
        </div>
      )}

      {/* Model legend */}
      <div className="flex flex-wrap gap-2 text-xs">
        {models.map((m) => (
          <span
            key={m.id}
            className={`px-2 py-1 rounded border ${
              m.location === "local"
                ? "border-success/30 bg-success/5 text-success dark:border-success/40 dark:bg-success/20 dark:text-success/70"
                : m.location === "cloud"
                ? "border-info/30 bg-info/5 text-info dark:border-info/40 dark:bg-info/20 dark:text-info/70"
                : "border-info/30 bg-info/5 text-info dark:border-info/40 dark:bg-info/20 dark:text-info/70"
            }`}
          >
            {m.id === "auto" ? "🔄" : m.location === "local" ? "🏠" : "☁️"}{" "}
            {m.name}
          </span>
        ))}
      </div>

      {/* Stage selector grid */}
      {categories.map((cat) => {
        const catStages = stages.filter((s) => s.category === cat.key);
        if (catStages.length === 0) return null;

        return (
          <div key={cat.key} className="space-y-1">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {cat.icon} {cat.label}
            </h4>
            <div className="grid gap-1">
              {catStages.map((stage) => {
                const selected = value[stage.name] || stage.default_model;
                return (
                  <div
                    key={stage.name}
                    className="flex items-center justify-between px-3 py-1.5 rounded-md border border-input bg-background hover:bg-muted/30 transition-colors"
                  >
                    <span className="text-sm">{stage.label}</span>
                    <div className="flex gap-1">
                      {models.map((m) => {
                        const isActive = selected === m.id;
                        return (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => handleStageChange(stage.name, m.id)}
                            className={`text-xs px-2 py-0.5 rounded border transition-all ${
                              isActive
                                ? m.location === "local"
                                  ? "border-success/40 bg-success/10 text-success dark:border-success/50 dark:bg-success/20 dark:text-success/70"
                                  : m.location === "cloud"
                                  ? "border-info/40 bg-info/10 text-info dark:border-info/50 dark:bg-info/20 dark:text-info/70"
                                  : "border-info/40 bg-info/10 text-info dark:border-info/50 dark:bg-info/20 dark:text-info/70"
                                : "border-input text-muted-foreground hover:border-muted-foreground/50"
                            }`}
                            title={m.name}
                          >
                            {m.id === "auto"
                              ? "Auto"
                              : m.location === "local"
                              ? "Local"
                              : "Cloud"}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
