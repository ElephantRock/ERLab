import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useResource } from "@/lib/useResource";
import {
  getStageModelConfig,
  updateStageModelConfig,
  resetStageModelConfig,
  type StageModelConfig,
} from "@/api/clients/models-client";

interface StageModelSelectorProps {
  /** Current assignments, passed up to parent form */
  value: Record<string, string>;
  onChange: (assignments: Record<string, string>) => void;
}

export function StageModelSelector({ value, onChange }: StageModelSelectorProps) {
  const [saving, setSaving] = useState(false);
  // Mutation 30: pending state for reset
  const [isResetting, setIsResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Fetch model config through the canonical typed client (F1.1 H1).
  // Previously this was a raw fetch() that bypassed apiFetchUnchecked's auth-header
  // injection (X-API-Key / JWT) and ApiError normalization — it would
  // silently fail in any deployment with auth enabled. The typed client
  // routes through apiFetchUnchecked + a runtime decoder.
  const resource = useResource<StageModelConfig>(
    ["settings", "models"],
    () => getStageModelConfig(),
  );

  const loading = resource.status === "loading";
  const config = resource.status === "ready" || resource.status === "empty"
    ? resource.data
    : null;

  // Propagate the server's saved assignments up to the parent form once the
  // config arrives (saved assignments take precedence over parent state on
  // first load). This is a render-synced side effect, not a fetch.
  const loadedAssignments =
    (resource.status === "ready" || resource.status === "empty")
      ? resource.data.assignments
      : null;
  useEffect(() => {
    if (loadedAssignments) {
      onChange({ ...loadedAssignments, ...value });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedAssignments]);

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
      await updateStageModelConfig(value);
      // Mutation 29: visible success feedback + cache invalidation so the
      // useResource read below re-fetches the saved assignments.
      toast.success("Configuration saved");
      queryClient.invalidateQueries({ queryKey: ["settings", "models"] });
    } catch {
      setError("Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    // Mutation 30: prevent duplicate submission while pending
    if (isResetting) return;
    setIsResetting(true);
    setError(null);
    try {
      await resetStageModelConfig();
      // Pessimistic: clear local state only AFTER the reset succeeds so a
      // failure leaves the user's unsaved assignments intact.
      onChange({});
      toast.success("Configuration reset to defaults");
      queryClient.invalidateQueries({ queryKey: ["settings", "models"] });
    } catch {
      setError("Reset failed");
    } finally {
      setIsResetting(false);
    }
  }

  if (loading) {
    return (
      <div className="text-sm text-muted-foreground py-2">
        Loading model configuration...
      </div>
    );
  }

  // Surface fetch failures explicitly (PRODUCT.md §6: if data failed to load,
  // it says so). Previously the swallowed error fell through to the "no
  // models configured" path, hiding a real failure behind an empty message.
  if (resource.status === "error") {
    return (
      <div className="text-sm text-destructive py-2">
        Failed to load models
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
            disabled={isResetting}
            className="text-xs text-muted-foreground hover:text-foreground px-2 py-1 rounded border border-input disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isResetting ? "Resetting..." : "Reset to Defaults"}
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
                            className={`text-xs px-2 py-0.5 rounded border transition-colors ${
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
