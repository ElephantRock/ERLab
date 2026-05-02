import { useState, useEffect, type ReactNode } from "react";
import { Sidebar, MobileBottomNav } from "./sidebar";
import { cn } from "@/lib/utils";
import { PanelLeftClose, PanelLeft, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlobalSearchDialog } from "@/components/search/global-search-dialog";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar — hidden on mobile via CSS */}
      <aside
        className={cn(
          "app-sidebar flex-shrink-0 border-r border-border transition-all duration-200 bg-card",
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
      <main className="app-main flex-1 overflow-auto">
        {/* Search button in header area */}
        <div className="flex items-center gap-2 border-b px-4 h-10">
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-2 text-muted-foreground"
            onClick={() => setSearchOpen(true)}
          >
            <Search className="h-3.5 w-3.5" />
            <span className="text-xs">Search…</span>
            <kbd className="pointer-events-none ml-1 inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
              ⌘K
            </kbd>
          </Button>
        </div>
        {children}
      </main>
      {/* Mobile bottom nav — shown on mobile via CSS */}
      <MobileBottomNav />
      <GlobalSearchDialog open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  );
}
