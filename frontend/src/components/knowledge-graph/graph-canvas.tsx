/**
 * GraphCanvas — SVG-based knowledge graph visualization (HB-01: client-side only).
 *
 * Renders entities as colored circles and relationships as lines.
 * No D3 dependency — pure SVG with React state for positioning.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import type { GraphEntity, GraphRelationship } from "@/api/knowledge-graph";

// ── Color map for entity types ────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  paper: "#3b82f6",
  author: "#10b981",
  method: "#f59e0b",
  dataset: "#8b5cf6",
  concept: "#ef4444",
};

const DEFAULT_COLOR = "#6b7280";
const NODE_RADIUS = 20;

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  entity: GraphEntity;
}

// ── Simple force-directed-like layout (deterministic placement) ───

function layoutNodes(entities: GraphEntity[], width: number, height: number): LayoutNode[] {
  const cx = width / 2;
  const cy = height / 2;

  return entities.map((entity, i) => {
    const angle = (2 * Math.PI * i) / Math.max(entities.length, 1);
    const radius = Math.min(width, height) * 0.35;
    return {
      id: entity.id,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      entity,
    };
  });
}

interface GraphCanvasProps {
  entities: GraphEntity[];
  relationships: GraphRelationship[];
  selectedId: string | null;
  onSelectEntity: (id: string) => void;
  className?: string;
}

export function GraphCanvas({
  entities,
  relationships,
  selectedId,
  onSelectEntity,
  className,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const [dragOffset, setDragOffset] = useState<{ x: number; y: number } | null>(null);
  const [dragNodeId, setDragNodeId] = useState<string | null>(null);

  const nodes = useMemo(
    () => layoutNodes(entities, dimensions.width, dimensions.height),
    [entities, dimensions.width, dimensions.height],
  );

  const nodeMap = useMemo(() => {
    const m = new Map<string, LayoutNode>();
    nodes.forEach((n) => m.set(n.id, n));
    return m;
  }, [nodes]);

  const handleResize = useCallback(() => {
    if (containerRef.current) {
      const { clientWidth, clientHeight } = containerRef.current;
      setDimensions({ width: clientWidth || 800, height: clientHeight || 500 });
    }
  }, []);

  // Mouse handlers for drag
  const handleMouseDown = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      e.stopPropagation();
      const node = nodeMap.get(nodeId);
      if (node) {
        setDragNodeId(nodeId);
        setDragOffset({ x: e.clientX - node.x, y: e.clientY - node.y });
      }
    },
    [nodeMap],
  );

  const handleMouseUp = useCallback(() => {
    setDragNodeId(null);
    setDragOffset(null);
  }, []);

  return (
    <div
      ref={containerRef}
      className={`relative border rounded-lg bg-background overflow-hidden ${className || ""}`}
      style={{ minHeight: 400 }}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        className="select-none"
      >
        {/* Edges */}
        {relationships.map((rel, i) => {
          const source = nodeMap.get(rel.source_id);
          const target = nodeMap.get(rel.target_id);
          if (!source || !target) return null;

          return (
            <line
              key={`edge-${i}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke={selectedId === rel.source_id || selectedId === rel.target_id ? "#3b82f6" : "#94a3b8"}
              strokeWidth={selectedId === rel.source_id || selectedId === rel.target_id ? 2 : 1}
              opacity={0.6}
            />
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const color = TYPE_COLORS[node.entity.entity_type] || DEFAULT_COLOR;
          const isSelected = node.id === selectedId;

          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              className="cursor-pointer"
              onClick={() => onSelectEntity(node.id)}
              onMouseDown={(e) => handleMouseDown(e, node.id)}
            >
              {/* Selection ring */}
              {isSelected && (
                <circle r={NODE_RADIUS + 4} fill="none" stroke="#3b82f6" strokeWidth={2} />
              )}
              <circle
                r={NODE_RADIUS}
                fill={color}
                opacity={0.85}
                className="transition-opacity duration-150 hover:opacity-100"
              />
              {/* Label */}
              <text
                textAnchor="middle"
                y={NODE_RADIUS + 14}
                className="text-xs fill-muted-foreground"
                fontSize={10}
              >
                {node.entity.name.length > 18
                  ? node.entity.name.slice(0, 16) + "…"
                  : node.entity.name}
              </text>
              {/* Type badge */}
              <text
                textAnchor="middle"
                y={4}
                className="text-white text-ui-micro font-bold pointer-events-none"
                fill="white"
                fontSize={8}
              >
                {node.entity.entity_type.slice(0, 3).toUpperCase()}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 bg-background/80 backdrop-blur-sm rounded-md px-2 py-1 text-xs text-muted-foreground">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
