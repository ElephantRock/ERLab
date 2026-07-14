import { useQuery } from "@tanstack/react-query";
import { getCatalog, getAssignments } from "@/api/settings";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorCard } from "@/components/ui/error-card";
import { Cpu, HardDrive, CheckCircle2, XCircle } from "lucide-react";

/**
 * Read-only panel showing loaded models, their capabilities,
 * and the current stage-to-model routing plan.
 *
 * Data sources (confirmed backend contracts):
 * - GET /api/v1/settings/catalog — discovered models + GPU info
 * - GET /api/v1/settings/assignments — stage→model routing
 */
export function ModelStatusPanel() {
  const {
    data: catalog,
    isLoading: catalogLoading,
    error: catalogError,
  } = useQuery({
    queryKey: ["model-catalog"],
    queryFn: getCatalog,
  });

  const {
    data: assignments,
    isLoading: assignmentsLoading,
    error: assignmentsError,
  } = useQuery({
    queryKey: ["model-assignments"],
    queryFn: getAssignments,
  });

  const error = catalogError || assignmentsError;

  if (error) {
    return (
      <Card data-testid="model-status-panel" className="card-shadow">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-1.5">
            <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">Models</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorCard message="Failed to load model status" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card data-testid="model-status-panel" className="card-shadow">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-1.5">
          <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-ui-micro font-semibold uppercase tracking-wider text-muted-foreground">Models</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* GPU Info */}
        {catalogLoading ? (
          <Skeleton className="h-8 w-full" />
        ) : catalog?.gpu ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <HardDrive className="h-4 w-4" />
            <span>{catalog.gpu.name}</span>
            <span className="text-xs">
              {catalog.gpu.vram_available_gb?.toFixed(1)} / {catalog.gpu.vram_total_gb?.toFixed(1)} GB free
            </span>
          </div>
        ) : null}

        {/* Model List */}
        {catalogLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : catalog?.models?.length ? (
          <div className="space-y-2">
            {catalog.models.map((model) => (
              <div
                key={model.model_id}
                className="flex items-center justify-between rounded-md border p-2"
                data-testid={`model-${model.model_id}`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {model.display_name}
                    </span>
                    {model.is_loaded ? (
                      <CheckCircle2
                        className="h-3 w-3 text-success flex-shrink-0"
                        aria-label="Loaded"
                      />
                    ) : (
                      <XCircle
                        className="h-3 w-3 text-muted-foreground flex-shrink-0"
                        aria-label="Not loaded"
                      />
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    <span className="text-xs text-muted-foreground">
                      {model.context_label || `${model.context_length} ctx`}
                    </span>
                    {model.quantization && (
                      <span className="text-xs text-muted-foreground">
                        · {model.quantization}
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">
                      · {model.size_gb.toFixed(1)} GB
                    </span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1 justify-end">
                  {model.capabilities.json_mode && (
                    <Badge variant="outline" className="text-xs">JSON</Badge>
                  )}
                  {model.capabilities.thinking && (
                    <Badge variant="outline" className="text-xs">Think</Badge>
                  )}
                  {model.capabilities.vision && (
                    <Badge variant="outline" className="text-xs">Vision</Badge>
                  )}
                  {model.capabilities.tools && (
                    <Badge variant="outline" className="text-xs">Tools</Badge>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground" data-testid="no-models">
            No models discovered. Configure a provider in settings.
          </p>
        )}

        {/* Stage Assignments Summary */}
        {assignmentsLoading ? (
          <Skeleton className="h-8 w-full" />
        ) : assignments?.assignments && Object.keys(assignments.assignments).length > 0 ? (
          <div className="pt-2 border-t" data-testid="stage-assignments">
            <p className="text-xs font-medium text-muted-foreground mb-2">
              Stage Routing ({assignments.total_stages} stages)
            </p>
            <div className="flex flex-wrap gap-1">
              {Object.entries(assignments.assignments).map(([stage, assignment]) => (
                <Badge
                  key={stage}
                  variant="secondary"
                  className="text-xs"
                  title={`${stage} → ${assignment.model_id}`}
                >
                  {stage.replace(/_/g, " ")}: {assignment.model_id}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
