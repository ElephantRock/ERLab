/**
 * TreeVisualization — SVG-based tree search visualization (BATCH-63/TASK-02).
 *
 * Renders tree search nodes as colored rectangles positioned by depth (x)
 * and index (y), with edges connecting parents to children.
 * Top-scored node is highlighted with a glow effect.
 * No additional API calls — renders from embedded tree_data (HB-02).
 *
 * Pattern: pure SVG with React state (same as graph-canvas.tsx from BATCH-25).
 */

import { useMemo, useState, useCallback } from "react";
import type { TreeData, TreeNode } from "@/api/types";

// ── Layout constants ────────────────────────────────────────────

const NODE_WIDTH = 180;
const NODE_HEIGHT = 56;
const NODE_RX = 8;
const HORIZONTAL_GAP = 220;
const VERTICAL_GAP = 72;
const MARGIN_X = 40;
const MARGIN_Y = 40;

// ── Score → color mapping ───────────────────────────────────────

function scoreColor(score: number): string {
  if (score >= 0.7) return "#22c55e"; // green — high
  if (score >= 0.4) return "#eab308"; // yellow — medium
  return "#ef4444"; // red — low
}

function scoreLabel(score: number): string {
  if (score >= 0.7) return "High";
  if (score >= 0.4) return "Medium";
  return "Low";
}

// ── Layout algorithm ────────────────────────────────────────────

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  node: TreeNode;
  isTop: boolean;
}

interface LayoutEdge {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  score: number;
}

function layoutTree(data: TreeData): { nodes: LayoutNode[]; edges: LayoutEdge[]; width: number; height: number } {
  const { nodes: rawNodes } = data;

  // Group nodes by depth (derived from parent_ids chain length)
  const depthMap = new Map<string, number>();
  const nodeMap = new Map<string, TreeNode>();

  // Compute depth for each node
  for (const node of rawNodes) {
    nodeMap.set(String(node.id), node);
  }

  function getDepth(id: string, visited: Set<string> = new Set()): number {
    if (depthMap.has(id)) return depthMap.get(id)!;
    if (visited.has(id)) return 0; // cycle guard
    visited.add(id);

    const node = nodeMap.get(id);
    if (!node || !node.parent_ids || node.parent_ids.length === 0) {
      depthMap.set(id, 0);
      return 0;
    }

    const parentDepth = Math.max(...node.parent_ids.map((pid) => getDepth(pid, visited)));
    const d = parentDepth + 1;
    depthMap.set(id, d);
    return d;
  }

  for (const node of rawNodes) {
    getDepth(String(node.id));
  }

  // Group by depth
  const byDepth = new Map<number, TreeNode[]>();
  let maxDepth = 0;
  for (const node of rawNodes) {
    const d = depthMap.get(String(node.id)) ?? 0;
    if (d > maxDepth) maxDepth = d;
    const group = byDepth.get(d) ?? [];
    group.push(node);
    byDepth.set(d, group);
  }

  // Find top-scored node
  let topScore = -Infinity;
  let topId = "";
  for (const node of rawNodes) {
    if (node.score > topScore) {
      topScore = node.score;
      topId = String(node.id);
    }
  }

  // Position nodes
  const layoutNodes: LayoutNode[] = [];
  for (let d = 0; d <= maxDepth; d++) {
    const group = byDepth.get(d) ?? [];
    const totalHeight = group.length * (NODE_HEIGHT + VERTICAL_GAP) - VERTICAL_GAP;
    const startY = MARGIN_Y + Math.max(0, (200 - totalHeight) / 2);

    for (let i = 0; i < group.length; i++) {
      const node: TreeNode = group[i]!;
      layoutNodes.push({
        id: String(node.id),
        x: MARGIN_X + d * HORIZONTAL_GAP,
        y: startY + i * (NODE_HEIGHT + VERTICAL_GAP),
        node,
        isTop: String(node.id) === topId,
      });
    }
  }

  // Build edges from parent_ids
  const layoutMap = new Map<string, LayoutNode>();
  for (const ln of layoutNodes) {
    layoutMap.set(ln.id, ln);
  }

  const edges: LayoutEdge[] = [];
  for (const ln of layoutNodes) {
    for (const pid of ln.node.parent_ids) {
      const parent = layoutMap.get(pid);
      if (parent) {
        edges.push({
          x1: parent.x + NODE_WIDTH,
          y1: parent.y + NODE_HEIGHT / 2,
          x2: ln.x,
          y2: ln.y + NODE_HEIGHT / 2,
          score: ln.node.score,
        });
      }
    }
  }

  // Compute SVG dimensions
  const maxX = Math.max(...layoutNodes.map((n) => n.x + NODE_WIDTH), 200);
  const maxY = Math.max(...layoutNodes.map((n) => n.y + NODE_HEIGHT), 200);

  return {
    nodes: layoutNodes,
    edges,
    width: maxX + MARGIN_X,
    height: maxY + MARGIN_Y,
  };
}

// ── Component ───────────────────────────────────────────────────

interface TreeVisualizationProps {
  tree_data: TreeData | null;
  className?: string;
}

export function TreeVisualization({ tree_data, className }: TreeVisualizationProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const layout = useMemo(() => {
    if (!tree_data || !tree_data.nodes || tree_data.nodes.length === 0) return null;
    return layoutTree(tree_data);
  }, [tree_data]);

  const handleMouseEnter = useCallback((id: string) => setHoveredId(id), []);
  const handleMouseLeave = useCallback(() => setHoveredId(null), []);

  // ── Empty state ──────────────────────────────────────────────
  if (!tree_data || !tree_data.nodes || tree_data.nodes.length === 0) {
    return (
      <div
        className="flex items-center justify-center p-12 text-muted-foreground border rounded-lg bg-background"
        data-testid="tree-empty"
      >
        <p>No tree data available for this run.</p>
      </div>
    );
  }

  if (!layout) return null;

  const { nodes, edges, width, height } = layout;

  return (
    <div
      className={`relative border rounded-lg bg-background overflow-auto ${className || ""}`}
      style={{ minHeight: 300 }}
      data-testid="tree-visualization"
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="select-none"
      >
        <defs>
          {/* Glow filter for top-scored node */}
          <filter id="top-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feFlood floodColor="#3b82f6" floodOpacity="0.5" result="color" />
            <feComposite in="color" in2="blur" operator="in" result="glow" />
            <feMerge>
              <feMergeNode in="glow" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Edges */}
        {edges.map((edge, i) => (
          <line
            key={`edge-${i}`}
            x1={edge.x1}
            y1={edge.y1}
            x2={edge.x2}
            y2={edge.y2}
            stroke={scoreColor(edge.score)}
            strokeWidth={2}
            opacity={0.5}
          />
        ))}

        {/* Nodes */}
        {nodes.map((ln) => {
          const color = scoreColor(ln.node.score);
          const isHovered = ln.id === hoveredId;

          return (
            <g
              key={ln.id}
              transform={`translate(${ln.x}, ${ln.y})`}
              className="cursor-pointer"
              onMouseEnter={() => handleMouseEnter(ln.id)}
              onMouseLeave={handleMouseLeave}
              data-testid={`tree-node-${ln.id}`}
            >
              {/* Top-scored highlight */}
              {ln.isTop && (
                <rect
                  x={-3}
                  y={-3}
                  width={NODE_WIDTH + 6}
                  height={NODE_HEIGHT + 6}
                  rx={NODE_RX + 2}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth={2.5}
                  filter="url(#top-glow)"
                  data-testid="top-scored-node"
                />
              )}

              {/* Node body */}
              <rect
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx={NODE_RX}
                fill={isHovered ? color : color}
                opacity={isHovered ? 1.0 : 0.85}
                className="transition-all duration-150"
              />

              {/* Title text (truncated) */}
              <text
                x={10}
                y={20}
                fontSize={11}
                fontWeight="600"
                fill="white"
                className="pointer-events-none"
              >
                {ln.node.title.length > 22
                  ? ln.node.title.slice(0, 20) + "…"
                  : ln.node.title}
              </text>

              {/* Score text */}
              <text
                x={10}
                y={38}
                fontSize={10}
                fill="white"
                opacity={0.9}
                className="pointer-events-none"
              >
                Score: {(ln.node.score * 100).toFixed(0)}% ({scoreLabel(ln.node.score)})
              </text>

              {/* Score badge */}
              <text
                x={NODE_WIDTH - 10}
                y={20}
                textAnchor="end"
                fontSize={10}
                fontWeight="700"
                fill="white"
                className="pointer-events-none"
              >
                {(ln.node.score * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip on hover */}
      {hoveredId && (() => {
        const hoveredNode = nodes.find((n) => n.id === hoveredId);
        if (!hoveredNode) return null;
        return (
          <div
            className="absolute bottom-3 right-3 bg-popover border rounded-lg shadow-lg p-3 text-sm max-w-xs z-10"
            data-testid="tree-tooltip"
          >
            <p className="font-semibold">{hoveredNode.node.title}</p>
            <p className="text-muted-foreground mt-1">
              Score: {(hoveredNode.node.score * 100).toFixed(1)}%
            </p>
            {hoveredNode.node.proposed_method && (
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                {hoveredNode.node.proposed_method}
              </p>
            )}
          </div>
        );
      })()}

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 bg-background/80 backdrop-blur-sm rounded-md px-2 py-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: "#22c55e" }} />
          High (≥0.7)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: "#eab308" }} />
          Medium (0.4–0.7)
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: "#ef4444" }} />
          Low (&lt;0.4)
        </span>
      </div>

      {/* Metadata */}
      {tree_data.config && (
        <div className="absolute top-2 right-2 text-xs text-muted-foreground bg-background/80 backdrop-blur-sm rounded-md px-2 py-1">
          beam_width={tree_data.config.beam_width} · max_depth={tree_data.config.max_depth} · {tree_data.nodes.length} nodes
        </div>
      )}
    </div>
  );
}
