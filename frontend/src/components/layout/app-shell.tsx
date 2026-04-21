import { useState, type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { cn } from "@/lib/utils";
import { PanelLeftClose, PanelLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <aside
        className={cn(
          "flex-shrink-0 border-r border-border transition-all duration-200 bg-card",
          collapsed ? "w-16" : "w-56",
        )}
      >
        <div className="flex items-center justify-between h-14 px-3 border-b">
          {!collapsed && (
            <span className="font-semibold text-sm truncate">Elephant Rock</span>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </Button>
        </div>
        <Sidebar collapsed={collapsed} />
      </aside>
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
