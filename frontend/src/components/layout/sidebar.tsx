import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Play,
  Lightbulb,
  GitBranch,
  Search,
  Settings,
  DollarSign,
  Brain,
  Shield,
  Activity,
  Layers,
  BookMarked,
  BrainCircuit,
  Cpu,
  Puzzle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
  /** Show in mobile bottom nav (limited space) */
  mobile?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Primary",
    items: [
      { to: "/", icon: LayoutDashboard, label: "Dashboard", mobile: true },
      { to: "/pipeline/new", icon: Play, label: "Pipeline", mobile: true },
      { to: "/ideas", icon: Lightbulb, label: "Ideas", mobile: true },
      { to: "/gaps", icon: GitBranch, label: "Gaps" },
    ],
  },
  {
    label: "Research Tools",
    items: [
      { to: "/literature", icon: BookMarked, label: "Literature" },
      { to: "/knowledge", icon: Search, label: "Knowledge" },
      { to: "/knowledge-graph", icon: BrainCircuit, label: "Graph" },
      { to: "/memory", icon: Brain, label: "Memory" },
      { to: "/autonomous", icon: Cpu, label: "Autonomous", mobile: true },
      { to: "/sessions", icon: Layers, label: "Sessions" },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/costs", icon: DollarSign, label: "Costs" },
      { to: "/governance", icon: Shield, label: "Governance" },
      { to: "/traces", icon: Activity, label: "Traces" },
      { to: "/plugins", icon: Puzzle, label: "Plugins" },
      { to: "/settings", icon: Settings, label: "Settings" },
    ],
  },
];

/** Flat list for mobile nav (backward compat) */
const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export { NAV_ITEMS };

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <nav className="p-2 space-y-4" data-testid="sidebar-nav">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="space-y-1">
          {!collapsed && (
            <div className="px-3 py-1 text-[0.625rem] font-semibold uppercase tracking-wider text-muted-foreground/60">
              {group.label}
            </div>
          )}
          {collapsed && (
            <div className="mx-auto my-1 h-px bg-border w-6" role="separator" />
          )}
          {group.items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )
              }
            >
              <item.icon className="h-4 w-4 flex-shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

/** Mobile bottom navigation — renders on small screens only. */
export function MobileBottomNav() {
  const mobileItems = NAV_ITEMS.filter((item) => item.mobile);

  return (
    <nav className="app-bottom-nav" aria-label="Mobile navigation">
      {mobileItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/"}
          className={({ isActive }) =>
            cn(
              "flex flex-col items-center gap-0.5 text-[0.625rem] px-1 py-1 rounded-md transition-colors",
              isActive
                ? "text-primary"
                : "text-muted-foreground hover:text-primary",
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
