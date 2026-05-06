import { useEffect, useCallback, useRef } from "react";

/**
 * Keyboard shortcut definitions.
 */
export interface KeyboardShortcut {
  key: string; // e.g., "j", "k", "/", "Escape", "?"
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  description: string;
  handler: () => void;
}

/**
 * useKeyboardShortcuts: Registers global keyboard shortcuts.
 *
 * Shortcuts:
 * - j: Navigate to next item
 * - k: Navigate to previous item
 * - /: Focus search
 * - Escape: Close modal/dialog
 * - ?: Show help overlay
 *
 * Shortcuts are only active when not typing in an input/textarea.
 */
export function useKeyboardShortcuts(
  shortcuts: KeyboardShortcut[],
  enabled: boolean = true,
): void {
  const shortcutsRef = useRef(shortcuts);
  shortcutsRef.current = shortcuts;

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return;

      // Ignore when typing in input/textarea
      const target = event.target as HTMLElement;
      if (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable
      ) {
        // Allow Escape even in inputs
        if (event.key !== "Escape") return;
      }

      for (const shortcut of shortcutsRef.current) {
        const keyMatch = event.key === shortcut.key;
        const ctrlMatch = shortcut.ctrl ? event.ctrlKey || event.metaKey : true;
        const metaMatch = shortcut.meta ? event.metaKey : true;
        const shiftMatch = shortcut.shift ? event.shiftKey : true;

        if (keyMatch && ctrlMatch && metaMatch && shiftMatch) {
          event.preventDefault();
          shortcut.handler();
          return;
        }
      }
    },
    [enabled],
  );

  useEffect(() => {
    if (!enabled) return;
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown, enabled]);
}

/**
 * Default shortcut definitions for Elephant Rock.
 */
export const DEFAULT_SHORTCUTS: Omit<KeyboardShortcut, "handler">[] = [
  { key: "j", description: "Navigate to next item" },
  { key: "k", description: "Navigate to previous item" },
  { key: "/", description: "Focus search" },
  { key: "Escape", description: "Close modal/dialog" },
  { key: "?", shift: true, description: "Show keyboard shortcuts" },
];

export default useKeyboardShortcuts;
