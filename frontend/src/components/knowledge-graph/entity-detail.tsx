/**
 * EntityDetail — detail panel for a selected knowledge graph entity.
 *
 * Shows entity properties, truth info, and connected relationships.
 */

import type { EntityDetail as EntityDetailType } from "@/api/knowledge-graph";
import { X, ExternalLink } from "lucide-react";

interface EntityDetailProps {
  detail: EntityDetailType;
  onClose: () => void;
  onNavigateToEntity?: (id: string) => void;
}

const TYPE_COLORS: Record<string, string> = {
  paper: "bg-info/10 text-info",
  author: "bg-success/10 text-success",
  method: "bg-warning/10 text-warning",
  dataset: "bg-info/10 text-info",
  concept: "bg-destructive/10 text-destructive",
};

export function EntityDetail({ detail, onClose, onNavigateToEntity }: EntityDetailProps) {
  const { entity, relationships } = detail;

  return (
    <div className="border rounded-lg bg-card p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                TYPE_COLORS[entity.entity_type] || "bg-muted/50 text-muted-foreground"
              }`}
            >
              {entity.entity_type}
            </span>
          </div>
          <h3 className="text-lg font-semibold leading-tight">{entity.name}</h3>
          {entity.aliases.length > 0 && (
            <p className="text-sm text-muted-foreground mt-1">
              Also known as: {entity.aliases.join(", ")}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-accent text-muted-foreground"
          aria-label="Close detail panel"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Truth */}
      <div className="space-y-1">
        <h4 className="text-sm font-medium text-muted-foreground">Truth Value</h4>
        <div className="flex gap-4 text-sm">
          <span>
            Confidence: <strong>{(entity.truth.confidence * 100).toFixed(0)}%</strong>
          </span>
          <span>
            Frequency: <strong>{(entity.truth.frequency * 100).toFixed(0)}%</strong>
          </span>
          <span>
            Sources: <strong>{entity.truth.source_count}</strong>
          </span>
        </div>
        {/* Confidence bar */}
        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full"
            style={{ width: `${entity.truth.confidence * 100}%` }}
          />
        </div>
      </div>

      {/* Properties */}
      {Object.keys(entity.properties).length > 0 && (
        <div className="space-y-1">
          <h4 className="text-sm font-medium text-muted-foreground">Properties</h4>
          <div className="text-sm space-y-0.5">
            {Object.entries(entity.properties).map(([key, value]) => (
              <div key={key}>
                <span className="text-muted-foreground">{key}:</span>{" "}
                <span>{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Relationships */}
      <div className="space-y-1">
        <h4 className="text-sm font-medium text-muted-foreground">
          Relationships ({relationships.length})
        </h4>
        {relationships.length === 0 ? (
          <p className="text-sm text-muted-foreground">No relationships found.</p>
        ) : (
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {relationships.map((rel, i) => {
              const isSource = rel.source_id === entity.id;
              const otherId = isSource ? rel.target_id : rel.source_id;
              return (
                <div
                  key={i}
                  className="flex items-center gap-2 text-sm py-1 px-2 rounded hover:bg-accent cursor-pointer"
                  onClick={() => onNavigateToEntity?.(otherId)}
                >
                  <ExternalLink className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                  <span className="text-muted-foreground">
                    {isSource ? "→" : "←"} {rel.relation_type}
                  </span>
                  <span className="font-mono text-xs">{otherId}</span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    w={rel.weight.toFixed(1)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
