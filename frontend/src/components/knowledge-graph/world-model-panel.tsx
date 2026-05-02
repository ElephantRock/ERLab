/**
 * WorldModelPanel — high-level world model summary.
 *
 * Displays top entities by confidence, strongest relationships,
 * and type distributions from the knowledge graph world model.
 */

import { Globe, TrendingUp, Link2 } from "lucide-react";
import type { WorldModel } from "@/api/knowledge-graph";

interface WorldModelPanelProps {
  model: WorldModel;
}

export function WorldModelPanel({ model }: WorldModelPanelProps) {
  return (
    <div className="border rounded-lg p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Globe className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-semibold">World Model</h2>
      </div>

      {/* Summary stats */}
      <div className="flex gap-3 text-sm">
        <span className="px-2.5 py-1 rounded-md bg-primary/10 text-primary font-medium">
          {model.total_entities} entities
        </span>
        <span className="px-2.5 py-1 rounded-md bg-primary/10 text-primary font-medium">
          {model.total_relationships} relationships
        </span>
      </div>

      {/* Entity type distribution */}
      {Object.keys(model.entity_type_distribution).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-1.5">
            Entity Types
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(model.entity_type_distribution).map(
              ([type, count]) => (
                <span
                  key={type}
                  className="px-2 py-0.5 rounded text-xs bg-muted"
                >
                  {type}: {count}
                </span>
              ),
            )}
          </div>
        </div>
      )}

      {/* Relationship type distribution */}
      {Object.keys(model.relationship_type_distribution).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-1.5">
            Relationship Types
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(model.relationship_type_distribution).map(
              ([type, count]) => (
                <span
                  key={type}
                  className="px-2 py-0.5 rounded text-xs bg-muted"
                >
                  {type}: {count}
                </span>
              ),
            )}
          </div>
        </div>
      )}

      {/* Top Entities */}
      {model.top_entities.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
            <TrendingUp className="h-3.5 w-3.5" />
            Top Entities
          </h3>
          <ul className="space-y-1.5">
            {model.top_entities.map((entity) => (
              <li
                key={entity.id}
                className="flex items-center justify-between text-sm"
              >
                <span className="truncate max-w-[200px]" title={entity.name}>
                  {entity.name}
                </span>
                <span className="text-xs text-muted-foreground ml-2">
                  {entity.entity_type} · {(entity.truth.confidence * 100).toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Strongest Relationships */}
      {model.strongest_relationships.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
            <Link2 className="h-3.5 w-3.5" />
            Strongest Relationships
          </h3>
          <ul className="space-y-1.5">
            {model.strongest_relationships.map((rel, idx) => (
              <li
                key={`${rel.source_id}-${rel.target_id}-${rel.relation_type}-${idx}`}
                className="text-xs text-muted-foreground"
              >
                <span className="font-medium text-foreground">
                  {rel.source_id}
                </span>{" "}
                →{" "}
                <span className="font-medium text-foreground">
                  {rel.target_id}
                </span>{" "}
                <span className="italic">({rel.relation_type})</span>
                <span className="ml-1">w={rel.weight.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
