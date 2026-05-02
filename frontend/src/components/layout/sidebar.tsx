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
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
  /** Show in mobile bottom nav (limited space) */
  mobile?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", mobile: true },
  { to: "/pipeline/new", icon: Play, label: "Pipeline", mobile: true },
  { to: "/ideas", icon: Lightbulb, label: "Ideas", mobile: true },
  { to: "/gaps", icon: GitBranch, label: "Gaps" },
  { to: "/knowledge", icon: Search, label: "Knowledge" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/costs", icon: DollarSign, label: "Costs" },
  { to: "/memory", icon: Brain, label: "Memory" },
  { to: "/governance", icon: Shield, label: "Governance" },
  { to: "/traces", icon: Activity, label: "Traces" },
  { to: "/sessions", icon: Layers, label: "Sessions" },
  { to: "/literature", icon: BookMarked, label: "Literature" },
  { to: "/knowledge-graph", icon: BrainCircuit, label: "Graph" },
  { to: "/autonomous", icon: Cpu, label: "Autonomous", mobile: true },
];

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <nav className="p-2 space-y-1">
      {NAV_ITEMS.map((item) => (
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
