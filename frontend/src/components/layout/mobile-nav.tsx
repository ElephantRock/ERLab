/**
 * MobileNav — full-IA mobile navigation via Sheet.
 *
 * INTERFACE_CONTRACT.md §5 Mobile (cites PRODUCT.md "Scope"):
 * Replaces the old MobileBottomNav (which exposed only 4 routes, leaving 13
 * unreachable). This Sheet exposes the full loop-based IA, so every route
 * is reachable on mobile. Target: 13 unreachable routes → 0.
 *
 * The bottom-nav shortcut bar keeps 4 high-frequency items for thumb reach:
 * DIRECT (New Run), TRIAGE (Results), GOVERN (Review), plus a Menu button
 * that opens the full Sheet.
 */

import { NavLink } from "react-router-dom";
import { Menu, Play, Archive, ShieldCheck } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { NAV_GROUPS } from "./sidebar";
import { cn } from "@/lib/utils";
import { useState } from "react";

/** Bottom-nav shortcuts: the 3 most frequent + a menu button for everything else. */
const SHORTCUTS = [
  { to: "/pipeline/new", icon: Play, label: "Run" },
  { to: "/ideas", icon: Archive, label: "Results" },
  { to: "/governance", icon: ShieldCheck, label: "Review" },
];

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Bottom-nav shortcut bar — always visible on mobile */}
      <nav className="app-bottom-nav" aria-label="Mobile navigation">
        {SHORTCUTS.map((item) => (
          <NavLink
            key={`shortcut-${item.to}`}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 px-1 py-1 rounded-md transition-colors",
                isActive ? "text-accent" : "text-muted-foreground hover:text-accent",
              )
            }
          >
            <item.icon className="h-5 w-5" />
            <span className="text-ui-micro">{item.label}</span>
          </NavLink>
        ))}

        {/* Menu button — opens the full IA Sheet */}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex flex-col items-center gap-0.5 px-1 py-1 rounded-md transition-colors text-muted-foreground hover:text-accent"
          aria-label="Open full navigation menu"
        >
          <Menu className="h-5 w-5" />
          <span className="text-ui-micro">Menu</span>
        </button>
      </nav>

      {/* Full IA Sheet — exposes every route, no orphans */}
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-72 overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="font-display">Elephant Rock</SheetTitle>
          </SheetHeader>

          <div className="px-3 pb-6">
            {NAV_GROUPS.map((group) => (
              <div key={group.label} className="mb-4">
                {/* Separator before Secondary */}
                {group.secondary && (
                  <div
                    className="my-3 h-px"
                    style={{ backgroundColor: "hsl(var(--border))" }}
                    role="separator"
                  />
                )}
                <h3 className="text-ui-micro font-semibold uppercase tracking-wider px-2 mb-1 text-muted-foreground">
                  {group.label}
                </h3>
                {group.items.map((item) => (
                  <NavLink
                    key={`mobile-sheet-${group.label}-${item.to}`}
                    to={item.to}
                    end={item.to === "/"}
                    onClick={() => setOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2.5 px-2 py-2 rounded transition-colors",
                        isActive
                          ? "bg-accent/10 text-accent font-medium"
                          : "text-foreground hover:bg-muted",
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" />
                    <span className="text-ui-label">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
