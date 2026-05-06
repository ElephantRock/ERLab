import { useState, useEffect, useCallback } from "react";

/**
 * useDarkMode: Manages dark/light theme with localStorage persistence.
 *
 * - Reads initial preference from localStorage or system preference
 * - Toggles between "dark" and "light" classes on <html>
 * - Persists choice to localStorage
 */
export function useDarkMode(defaultDark: boolean = false): {
  isDark: boolean;
  toggle: () => void;
  setDark: (dark: boolean) => void;
} {
  const [isDark, setIsDark] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem("elephant-rock-theme");
      if (stored) return stored === "dark";
      return (
        defaultDark ||
        window.matchMedia("(prefers-color-scheme: dark)").matches
      );
    } catch {
      return defaultDark;
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add("dark");
      root.classList.remove("light");
    } else {
      root.classList.add("light");
      root.classList.remove("dark");
    }
    try {
      localStorage.setItem("elephant-rock-theme", isDark ? "dark" : "light");
    } catch {
      // localStorage unavailable — ignore
    }
  }, [isDark]);

  const toggle = useCallback(() => setIsDark((prev) => !prev), []);
  const setDark = useCallback((dark: boolean) => setIsDark(dark), []);

  return { isDark, toggle, setDark };
}

export default useDarkMode;
