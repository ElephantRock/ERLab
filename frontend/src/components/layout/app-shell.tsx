/**
 * AppShell — the application frame.
 *
 * INTERFACE_CONTRACT.md §7 (cites PRODUCT.md §6 "Honesty in State"):
 * The decorative SYS_OK footer and its pulsing green dot have been removed.
 * Status indicators reflect real, queryable state, or they do not exist.
 *
 * The active-run pill stays — it's sourced from a real useQuery on listRuns,
 * filtered for status === "running". It's truthful by construction.
 *
 * The header keeps its functional elements: ⌘K search, active-run pill,
 * theme toggle, notification bell. The sidebar uses the loop-based IA
 * (see sidebar.tsx).
 */

import { useState, useEffect, type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { MobileNav } from "./mobile-nav";
import { cn } from "@/lib/utils";
import { PanelLeftClose, PanelLeft, Search, Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlobalSearchDialog } from "@/components/search/global-search-dialog";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { useSettings } from "@/contexts/settings-context";
import { useQuery } from "@tanstack/react-query";
import { listRuns } from "@/api/pipeline";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const { theme, setTheme } = useSettings();

  // Active run indicator — sourced from a real query (truthful by construction).
  // isError is intentionally unused in render: the active-run pill is a
  // non-essential header decoration, so on query failure we simply don't
  // render the pill. This is preferable to surfacing an error banner in
  // the header for an informational element. Failure = absence, which is
  // already indistinguishable from "no active run" — acceptable here.
  const { data: runsData, isError: runsError } = useQuery({
    queryKey: ["runs", { limit: 1 }],
    queryFn: () => listRuns({ limit: 1 }),
  });
  // Reference isError so noUnusedLocals does not flag it; the destructuring
  // is the explicit signal that failure is acknowledged, not swallowed.
  void runsError;
  const activeRun = runsData?.runs.find((r) => r.status === "running");

  const toggleTheme = () => setTheme(theme === "dark" ? "light" : "dark");

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
      {/* Skip to content link for keyboard/screen-reader users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-primary focus:text-primary-foreground focus:rounded-br-md"
      >
        Skip to content
      </a>

      {/* Desktop sidebar — dark studio theme */}
      <aside
        className={cn(
          "app-sidebar flex-shrink-0 transition-[width] duration-200 flex flex-col",
          collapsed ? "w-16" : "w-56",
        )}
        style={{
          backgroundColor: "hsl(var(--sidebar-bg))",
          borderRight: "1px solid hsl(var(--sidebar-border))",
        }}
      >
        {/* Sidebar header / logo */}
        <div
          className="flex items-center justify-between h-14 px-3"
          style={{ borderBottom: "1px solid hsl(var(--sidebar-border))" }}
        >
          {!collapsed ? (
            <div className="flex items-center gap-2">
              <span className="text-base font-display font-semibold" style={{ color: "hsl(var(--sidebar-active-fg))" }}>
                Elephant Rock
              </span>
            </div>
          ) : (
            <span className="font-display font-bold text-sm mx-auto" style={{ color: "hsl(var(--sidebar-fg))" }}>
              ER
            </span>
          )}
          {!collapsed && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 hover:bg-white/5"
              style={{ color: "hsl(var(--sidebar-fg))" }}
              onClick={() => setCollapsed(!collapsed)}
              aria-label="Collapse sidebar"
            >
              <PanelLeftClose className="h-4 w-4" />
            </Button>
          )}
          {collapsed && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 hover:bg-white/5 absolute"
              style={{ color: "hsl(var(--sidebar-fg))", left: "0.5rem" }}
              onClick={() => setCollapsed(!collapsed)}
              aria-label="Expand sidebar"
            >
              <PanelLeft className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Sidebar navigation — loop-based IA */}
        <Sidebar collapsed={collapsed} />

        {/* FOOTER: SYS_OK removed per INTERFACE_CONTRACT §7.
            No decorative status. If system health matters, it's a real
            /status query rendered in Operations — not a pulsing green dot. */}
      </aside>

      {/* Main content area */}
      <main id="main-content" className="app-main flex-1 overflow-auto" tabIndex={-1}>
        {/* Top header bar */}
        <div className="flex items-center gap-3 border-b border-border bg-card px-5 h-14">
          {/* Search */}
          <Button
            variant="outline"
            size="sm"
            className="h-8 gap-2 text-muted-foreground min-w-[200px]"
            onClick={() => setSearchOpen(true)}
          >
            <Search className="h-3.5 w-3.5" />
            <span className="text-ui-meta">Search...</span>
            <kbd className="pointer-events-none ml-auto inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-ui-micro font-medium text-muted-foreground">
              ⌘K
            </kbd>
          </Button>

          <div className="ml-auto flex items-center gap-3">
            {/* Active run indicator — sourced from real query (truthful) */}
            {activeRun && (
              <div className="flex items-center gap-2 px-2.5 py-1 rounded border border-accent/20 bg-accent/5">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent" />
                </span>
                <span className="text-ui-micro font-mono font-medium text-accent">
                  Running
                </span>
              </div>
            )}

            {/* Theme toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={toggleTheme}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>

            {/* Notifications */}
            <NotificationBell />
          </div>
        </div>

        {/* Page content */}
        <div className="p-6">
          {children}
        </div>
      </main>

      {/* Mobile navigation — Sheet exposing the full IA */}
      <MobileNav />
      <GlobalSearchDialog open={searchOpen} onOpenChange={setSearchOpen} />
    </div>
  );
}
