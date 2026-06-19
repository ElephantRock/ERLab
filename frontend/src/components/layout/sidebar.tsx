import { NavLink } from "react-router-dom";
import {
  Compass,
  Play,
  Archive,
  ShieldCheck,
  Layers,
  BookOpen,
  GitFork,
  Gauge,
  Settings,
  CreditCard,
  Activity,
  Brain,
  Clock,
  Puzzle,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
  mobile?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
  collapsedByDefault?: boolean;
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Studio",
    items: [
      { to: "/", icon: Compass, label: "Home", mobile: true },
      { to: "/pipeline/new", icon: Play, label: "New Run", mobile: true },
      { to: "/ideas", icon: Archive, label: "Results", mobile: true },
      { to: "/governance", icon: ShieldCheck, label: "Review" },
    ],
  },
  {
    label: "Research",
    items: [
      { to: "/gaps", icon: Layers, label: "Gaps" },
      { to: "/literature", icon: BookOpen, label: "Literature" },
      { to: "/knowledge-graph", icon: GitFork, label: "Knowledge Graph" },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/ops", icon: Gauge, label: "Operations" },
      { to: "/settings", icon: Settings, label: "Settings", mobile: true },
    ],
  },
  {
    label: "Advanced",
    collapsedByDefault: true,
    items: [
      { to: "/costs", icon: CreditCard, label: "Costs" },
      { to: "/traces", icon: Activity, label: "Traces" },
      { to: "/memory", icon: Brain, label: "Memory" },
      { to: "/autonomous", icon: Clock, label: "Autonomous" },
      { to: "/plugins", icon: Puzzle, label: "Plugins" },
      { to: "/sessions", icon: Clock, label: "Sessions" },
    ],
  },
];

/** Flat list for mobile nav (backward compat) */
const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

// Deduplicate for mobile (Models/Settings point to same route)
const MOBILE_ITEMS = NAV_ITEMS.filter((item) => item.mobile);

export { NAV_ITEMS };

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <nav className="flex-1 overflow-y-auto py-4 px-3 scrollbar-thin" data-testid="sidebar-nav">
      {NAV_GROUPS.map((group) => (
        <NavGroupSection key={group.label} group={group} collapsed={collapsed} />
      ))}
    </nav>
  );
}

function NavGroupSection({
  group,
  collapsed,
}: {
  group: NavGroup;
  collapsed: boolean;
}) {
  const [isExpanded, setIsExpanded] = useState(!group.collapsedByDefault);

  // Non-collapsible groups
  if (!group.collapsedByDefault) {
    return (
      <div className="mb-5 space-y-1">
        {!collapsed && (
          <h3
            className="text-[10px] font-bold uppercase tracking-widest px-2 mb-1.5 font-mono"
            style={{ color: "hsl(0 0% 38%)" }}
          >
            {group.label}
          </h3>
        )}
        {collapsed && (
          <div className="mx-auto my-2 h-px w-6" style={{ backgroundColor: "hsl(var(--sidebar-border))" }} role="separator" />
        )}
        {group.items.map((item) => (
          <NavLink
            key={`${group.label}-${item.to}-${item.label}`}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 px-2 py-1.5 text-xs rounded transition-all duration-150",
                isActive
                  ? "font-medium"
                  : "hover:bg-white/5",
              )
            }
            style={({ isActive }) => ({
              backgroundColor: isActive ? "hsl(var(--sidebar-active))" : "transparent",
              color: isActive ? "hsl(var(--sidebar-active-fg))" : "hsl(0 0% 55%)",
            })}
          >
            {({ isActive }) => (
              <>
                {isActive ? (
                  <span className="h-1.5 w-1.5 rounded-full bg-accent shrink-0" style={{ backgroundColor: "hsl(var(--accent))" }} />
                ) : (
                  <item.icon className="h-3.5 w-3.5 shrink-0" style={{ color: "hsl(0 0% 40%)" }} />
                )}
                {!collapsed && <span className="truncate">{item.label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </div>
    );
  }

  // Collapsible group (Advanced)
  return (
    <div className="mb-5" data-testid={`nav-group-${group.label.toLowerCase()}`}>
      {!collapsed ? (
        <>
          <button
            onClick={() => setIsExpanded((v) => !v)}
            className="flex w-full items-center gap-1 px-2 py-1.5 text-[10px] font-bold uppercase tracking-widest font-mono transition-colors"
            style={{ color: "hsl(0 0% 38%)" }}
            aria-expanded={isExpanded}
            aria-label={`Toggle ${group.label}`}
            data-testid={`toggle-${group.label.toLowerCase()}`}
          >
            {isExpanded
              ? <ChevronDown className="h-3 w-3" />
              : <ChevronRight className="h-3 w-3" />
            }
            {group.label}
          </button>
          {isExpanded &&
            group.items.map((item) => (
              <NavLink
                key={`${group.label}-${item.to}-${item.label}`}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 px-2 py-1 text-xs rounded transition-all",
                    isActive ? "font-medium" : "hover:bg-white/5",
                  )
                }
                style={({ isActive }) => ({
                  backgroundColor: isActive ? "hsl(var(--sidebar-active))" : "transparent",
                  color: isActive ? "hsl(var(--sidebar-active-fg))" : "hsl(0 0% 45%)",
                })}
              >
                <item.icon className="h-3 w-3 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            ))}
        </>
      ) : (
        <>
          <div className="mx-auto my-2 h-px w-6" style={{ backgroundColor: "hsl(var(--sidebar-border))" }} role="separator" />
          {group.items.map((item) => (
            <NavLink
              key={`${group.label}-${item.to}-${item.label}`}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-center px-2 py-1.5 text-xs rounded transition-all",
                  isActive ? "font-medium" : "hover:bg-white/5",
                )
              }
              style={({ isActive }) => ({
                backgroundColor: isActive ? "hsl(var(--sidebar-active))" : "transparent",
                color: isActive ? "hsl(var(--sidebar-active-fg))" : "hsl(0 0% 45%)",
              })}
            >
              <item.icon className="h-3.5 w-3.5 shrink-0" />
            </NavLink>
          ))}
        </>
      )}
    </div>
  );
}

/** Mobile bottom navigation */
export function MobileBottomNav() {
  return (
    <nav className="app-bottom-nav" aria-label="Mobile navigation">
      {MOBILE_ITEMS.map((item) => (
        <NavLink
          key={`mobile-${item.to}-${item.label}`}
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) =>
            cn(
              "flex flex-col items-center gap-0.5 text-[0.625rem] px-1 py-1 rounded-md transition-colors",
              isActive ? "text-accent" : "text-muted-foreground hover:text-accent",
            )
          }
        >
          <item.icon className="h-5 w-5" />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}
