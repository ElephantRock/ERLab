import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Play,
  Lightbulb,
  GitBranch,
  Search,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/pipeline/new", icon: Play, label: "Pipeline" },
  { to: "/ideas", icon: Lightbulb, label: "Ideas" },
  { to: "/gaps", icon: GitBranch, label: "Gaps" },
  { to: "/knowledge", icon: Search, label: "Knowledge" },
  { to: "/settings", icon: Settings, label: "Settings" },
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
