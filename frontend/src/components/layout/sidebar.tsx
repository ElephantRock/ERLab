/**
 * Sidebar — navigation organized by PRODUCT.md's Core Loop.
 *
 * INTERFACE_CONTRACT.md §5 (cites PRODUCT.md "The Core Loop"):
 * Groups are derived from the researcher's workflow, not the backend's
 * feature buckets. The old IA (Studio/Research/System/Advanced) was "The
 * Mirror" anti-pattern — it reproduced the backend's structure. This IA
 * mirrors the loop: DIRECT → TRIAGE → READ → REFINE → GOVERN.
 *
 * Key property: Reading has no top-level destination — it's reached
 * THROUGH triage. You don't navigate TO a proposal; you navigate FROM
 * a result. The proposal workspace (/ideas/:id) has no nav entry by design.
 *
 * /knowledge (Knowledge Search) enters the READ group — it was previously
 * orphaned (a real page with no nav entry, violating "The Orphan Route").
 *
 * Secondary surfaces (Operations, Costs, Traces, Memory, Knowledge Graph,
 * Plugins, Settings) sit below a separator — reachable and functional but
 * explicitly do not set the visual tone (PRODUCT.md "Scope").
 */

import { NavLink } from "react-router-dom";
import {
  Compass,
  Play,
  Clock,
  Archive,
  Layers,
  BookOpen,
  Search,
  History,
  ShieldCheck,
  Gauge,
  CreditCard,
  Activity,
  Brain,
  GitFork,
  Puzzle,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
  /** Secondary groups render below a separator (PRODUCT.md "Scope"). */
  secondary?: boolean;
}

/**
 * Loop-based IA. Every page has exactly one nav home — no orphans.
 * The proposal workspace (/ideas/:id) and run detail (/runs/:id) are
 * intentionally absent: they're reached THROUGH triage/direct, not navigated to.
 */
const NAV_GROUPS: NavGroup[] = [
  {
    label: "Direct",
    items: [
      { to: "/", icon: Compass, label: "Dashboard" },
      { to: "/pipeline/new", icon: Play, label: "New Run" },
      { to: "/autonomous", icon: Clock, label: "Autonomous" },
    ],
  },
  {
    label: "Triage",
    items: [
      { to: "/ideas", icon: Archive, label: "Results" },
      { to: "/gaps", icon: Layers, label: "Gaps" },
      { to: "/literature", icon: BookOpen, label: "Literature" },
    ],
  },
  {
    label: "Read",
    items: [
      // Knowledge Search enters READ — previously orphaned.
      // The proposal workspace (/ideas/:id) has no nav entry: reached FROM triage.
      { to: "/knowledge", icon: Search, label: "Knowledge Search" },
    ],
  },
  {
    label: "Refine",
    items: [
      // Refinement is contextual (on the artifact). Sessions is the only
      // refinement surface that's a destination (cross-artifact history).
      { to: "/sessions", icon: History, label: "Sessions" },
    ],
  },
  {
    label: "Govern",
    items: [
      { to: "/governance", icon: ShieldCheck, label: "Review" },
      // Export is an action, not a destination — no nav entry.
    ],
  },
  // ── Separator ──────────────────────────────────────────────
  {
    label: "Secondary",
    secondary: true,
    items: [
      { to: "/ops", icon: Gauge, label: "Operations" },
      { to: "/costs", icon: CreditCard, label: "Costs" },
      { to: "/traces", icon: Activity, label: "Traces" },
      { to: "/memory", icon: Brain, label: "Memory" },
      { to: "/knowledge-graph", icon: GitFork, label: "Knowledge Graph" },
      { to: "/plugins", icon: Puzzle, label: "Plugins" },
      { to: "/settings", icon: Settings, label: "Settings" },
    ],
  },
];

/** The full nav structure — exported for MobileNav's Sheet rendering. */
export { NAV_GROUPS };

/** Flat list of all nav items (for reachability checks + mobile sheet). */
export const ALL_NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

/** All routes reachable from the nav (for orphan-route auditing). */
export const ALL_NAV_ROUTES: string[] = ALL_NAV_ITEMS.map((i) => i.to);

interface SidebarProps {
  collapsed: boolean;
}

export function Sidebar({ collapsed }: SidebarProps) {
  const primaryGroups = NAV_GROUPS.filter((g) => !g.secondary);
  const secondaryGroup = NAV_GROUPS.find((g) => g.secondary);

  return (
    <nav className="flex-1 overflow-y-auto py-4 px-3 scrollbar-thin" data-testid="sidebar-nav">
      {primaryGroups.map((group) => (
        <NavGroupSection key={group.label} group={group} collapsed={collapsed} />
      ))}

      {/* Separator before Secondary (PRODUCT.md "Scope": reachable but not tonal) */}
      <div
        className="my-3 h-px"
        style={{ backgroundColor: "hsl(var(--sidebar-border))" }}
        role="separator"
        aria-label="Secondary navigation"
      />

      {secondaryGroup && (
        <NavGroupSection group={secondaryGroup} collapsed={collapsed} />
      )}
    </nav>
  );
}

function NavGroupSection({ group, collapsed }: { group: NavGroup; collapsed: boolean }) {
  return (
    <div className="mb-4 space-y-0.5" data-testid={`nav-group-${group.label.toLowerCase()}`}>
      {!collapsed && (
        <h3 className="text-ui-micro font-semibold uppercase tracking-wider px-2 mb-1 text-muted-foreground">
          {group.label}
        </h3>
      )}
      {collapsed && (
        <div
          className="mx-auto my-2 h-px w-6"
          style={{ backgroundColor: "hsl(var(--sidebar-border))" }}
          role="separator"
        />
      )}
      {group.items.map((item) => (
        <NavLink
          key={`${group.label}-${item.to}`}
          to={item.to}
          end={item.to === "/"}
          className={() =>
            cn(
              "flex items-center gap-2.5 px-2 py-1.5 rounded transition-colors duration-150",
              collapsed && "justify-center",
            )
          }
          style={({ isActive }) => ({
            backgroundColor: isActive ? "hsl(var(--sidebar-active))" : "transparent",
            color: isActive ? "hsl(var(--sidebar-active-fg))" : "hsl(var(--sidebar-fg))",
          })}
        >
          {({ isActive }) => (
            <>
              <item.icon
                className={cn("shrink-0", collapsed ? "h-4 w-4" : "h-3.5 w-3.5")}
                style={{ color: isActive ? "hsl(var(--sidebar-active-fg))" : "hsl(var(--sidebar-fg))", opacity: isActive ? 1 : 0.7 }}
              />
              {!collapsed && (
                <span className={cn("text-ui-label truncate", isActive && "font-medium")}>
                  {item.label}
                </span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </div>
  );
}
