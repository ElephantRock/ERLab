/**
 * StageModelEditor — Editable table for per-stage model routing.
 *
 * Shows all 16 pipeline stages with a model dropdown per stage.
 * Certifications are shown as badges. Warnings appear for uncertified
 * assignments. Supports dry-run validation before saving.
 *
 * Phase B: Editable Model Routing UI.
 */

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getCatalog,
  getCertification,
  getStages,
  getOverrides,
  updateOverrides,
  removeOverride,
  clearAllOverrides,
} from "@/api/settings";
import type { OverrideWarning } from "@/api/settings";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorCard } from "@/components/ui/error-card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Save,
  Loader2,
  Pencil,
  X,
} from "lucide-react";

export function StageModelEditor() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [warnings, setWarnings] = useState<OverrideWarning[]>([]);

  // ── Queries ──────────────────────────────────────────────────

  const { data: stagesData, isLoading: stagesLoading } = useQuery({
    queryKey: ["stage-metadata"],
    queryFn: getStages,
  });

  const { data: catalogData, isLoading: catalogLoading } = useQuery({
    queryKey: ["model-catalog"],
    queryFn: getCatalog,
  });

  const { data: certData } = useQuery({
    queryKey: ["certification"],
    queryFn: getCertification,
  });

  const { data: overridesData } = useQuery({
    queryKey: ["model-overrides"],
    queryFn: getOverrides,
  });

  // ── Derived data ─────────────────────────────────────────────

  const modelOptions = useMemo(() => {
    if (!catalogData?.models) return [];
    return catalogData.models.filter((m) => m.health_status !== "unreachable");
  }, [catalogData]);

  // Map: model_id → set of certified stages
  const certMap = useMemo(() => {
    const map = new Map<string, Set<string>>();
    if (!certData?.certifications) return map;
    for (const cert of certData.certifications) {
      const stages = new Set<string>();
      for (const [stage, level] of Object.entries(cert.allowed_stages)) {
        if (level !== "not_approved" && level !== "blocked") {
          stages.add(stage);
        }
      }
      map.set(cert.model_id, stages);
    }
    return map;
  }, [certData]);

  const overrides = overridesData?.overrides ?? {};
  const stages = stagesData?.stages ?? [];

  // Current display state: draft overrides if editing, saved overrides otherwise
  const displayOverrides = editing ? draft : overrides;

  // ── Mutations ────────────────────────────────────────────────

  const saveMutation = useMutation({
    mutationFn: (body: Record<string, string>) => updateOverrides(body, false),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["model-overrides"] });
      setEditing(false);
      setWarnings([]);
      if (data.warnings.length > 0) {
        toast.warning(`Saved with ${data.warnings.length} warning(s)`);
        setWarnings(data.warnings);
      } else {
        toast.success("Model routing saved");
      }
    },
    onError: () => toast.error("Failed to save model routing"),
  });

  const removeMutation = useMutation({
    mutationFn: (stage: string) => removeOverride(stage),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-overrides"] });
      toast.success("Stage reset to auto-routing");
    },
    onError: () => toast.error("Failed to reset stage"),
  });

  const clearAllMutation = useMutation({
    mutationFn: () => clearAllOverrides(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-overrides"] });
      toast.success("All stage overrides cleared");
    },
    onError: () => toast.error("Failed to clear overrides"),
  });

  // ── Handlers ─────────────────────────────────────────────────

  function handleStartEdit() {
    setDraft({ ...overrides });
    setWarnings([]);
    setEditing(true);
  }

  function handleCancelEdit() {
    setDraft({});
    setWarnings([]);
    setEditing(false);
  }

  function handleStageChange(stage: string, modelId: string) {
    const newDraft = { ...draft };
    if (modelId === "") {
      delete newDraft[stage];
    } else {
      newDraft[stage] = modelId;
    }
    setDraft(newDraft);

    // Inline validation for the changed stage
    const certified = certMap.get(modelId);
    if (modelId && certified && !certified.has(stage)) {
      setWarnings((prev) => [
        ...prev.filter((w) => w.stage !== stage),
        {
          code: "NOT_CERTIFIED",
          stage,
          model_id: modelId,
          message: `Model '${modelId}' is not certified for '${stage}'.`,
        },
      ]);
    } else {
      setWarnings((prev) => prev.filter((w) => w.stage !== stage));
    }
  }

  function handleSave() {
    // Only save if there are changes
    let hasChanges = false;
    for (const [stage, modelId] of Object.entries(draft)) {
      if (overrides[stage] !== modelId) {
        hasChanges = true;
        break;
      }
    }
    if (!hasChanges) {
      // Check for deleted stages
      for (const stage of Object.keys(overrides)) {
        if (!(stage in draft)) {
          hasChanges = true;
          break;
        }
      }
    }
    if (!hasChanges) {
      toast.info("No changes to save");
      setEditing(false);
      return;
    }
    saveMutation.mutate(draft);
  }

  // ── Render ───────────────────────────────────────────────────

  if (stagesLoading || catalogLoading) {
    return (
      <Card data-testid="stage-model-editor" className="card-shadow">
        <CardHeader>
          <CardTitle className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">Stage Model Routing</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!catalogData || catalogData.error) {
    return (
      <Card data-testid="stage-model-editor" className="card-shadow">
        <CardHeader>
          <CardTitle className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">Stage Model Routing</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorCard message="No models available. Configure a provider first." />
        </CardContent>
      </Card>
    );
  }

  const categoryColors: Record<string, string> = {
    thinking: "bg-info/10 text-info",
    generation: "bg-success/10 text-success",
    passthrough: "bg-muted/50 text-muted-foreground",
  };

  return (
    <Card data-testid="stage-model-editor" className="card-shadow">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">Stage Model Routing</CardTitle>
          <div className="flex items-center gap-2">
            {editing ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCancelEdit}
                  data-testid="cancel-edit"
                >
                  <X className="h-3 w-3 mr-1" />
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleSave}
                  disabled={saveMutation.isPending}
                  data-testid="save-overrides"
                >
                  {saveMutation.isPending ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <Save className="h-3 w-3 mr-1" />
                  )}
                  Save
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => clearAllMutation.mutate()}
                  disabled={clearAllMutation.isPending || Object.keys(overrides).length === 0}
                  data-testid="reset-all"
                >
                  <RotateCcw className="h-3 w-3 mr-1" />
                  Reset All
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleStartEdit}
                  data-testid="edit-overrides"
                >
                  <Pencil className="h-3 w-3 mr-1" />
                  Edit
                </Button>
              </>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-1">
        {/* Warnings */}
        {warnings.length > 0 && (
          <div className="rounded-md border border-warning/30 bg-warning/5 p-3 mb-3" data-testid="warnings-panel">
            {warnings.map((w, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs">
                <AlertTriangle className="h-3 w-3 text-warning flex-shrink-0 mt-0.5" />
                <span className="text-muted-foreground">{w.message}</span>
              </div>
            ))}
          </div>
        )}

        {/* Stage rows */}
        {stages.filter((s) => s.needs_llm).map((stage) => {
          const currentModel = displayOverrides[stage.name];
          const isCertified = currentModel
            ? (certMap.get(currentModel)?.has(stage.name) ?? false)
            : true;
          const hasOverride = !!overrides[stage.name];

          return (
            <div
              key={stage.name}
              className="flex items-center gap-3 py-1.5 border-b last:border-0"
              data-testid={`stage-row-${stage.name}`}
            >
              {/* Stage name */}
              <div className="w-40 flex-shrink-0">
                <span className="text-sm font-medium">{stage.label}</span>
                <Badge
                  variant="outline"
                  className={`ml-1.5 text-xs ${categoryColors[stage.category]}`}
                >
                  {(stage.category[0] ?? "").toUpperCase()}
                </Badge>
              </div>

              {/* Model selector / display */}
              <div className="flex-1 min-w-0">
                {editing ? (
                  <select
                    value={currentModel ?? ""}
                    onChange={(e) => handleStageChange(stage.name, e.target.value)}
                    className="w-full text-sm border rounded px-2 py-1 bg-background"
                    data-testid={`model-select-${stage.name}`}
                  >
                    <option value="">Auto (fitness-scored)</option>
                    {modelOptions.map((model) => {
                      const certified = certMap.get(model.model_id);
                      const stageCertified = certified?.has(stage.name) ?? false;
                      return (
                        <option key={model.model_id} value={model.model_id}>
                          {model.display_name}
                          {stageCertified ? " ✓" : " (uncertified)"}
                        </option>
                      );
                    })}
                  </select>
                ) : (
                  <div className="flex items-center gap-2">
                    {currentModel ? (
                      <>
                        <span className="text-sm truncate">{currentModel}</span>
                        {isCertified ? (
                          <CheckCircle2
                            className="h-3 w-3 text-success flex-shrink-0"
                            aria-label="Certified"
                          />
                        ) : (
                          <AlertTriangle
                            className="h-3 w-3 text-warning flex-shrink-0"
                            aria-label="Not certified"
                          />
                        )}
                      </>
                    ) : (
                      <span className="text-sm text-muted-foreground">
                        Auto (fitness-scored)
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Reset single stage (non-editing mode only) */}
              {!editing && hasOverride && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-muted-foreground"
                  onClick={() => removeMutation.mutate(stage.name)}
                  disabled={removeMutation.isPending}
                  data-testid={`reset-stage-${stage.name}`}
                  title="Reset to auto"
                >
                  <RotateCcw className="h-3 w-3" />
                </Button>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
