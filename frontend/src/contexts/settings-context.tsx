import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { getApiUrl, getApiKey } from "@/api/client";

interface Settings {
  apiUrl: string;
  apiKey: string;
  theme: "light" | "dark";
}

interface SettingsContextValue extends Settings {
  setApiUrl: (url: string) => void;
  setApiKey: (key: string) => void;
  setTheme: (theme: "light" | "dark") => void;
}

const SettingsContext = createContext<SettingsContextValue | null>(null);

function loadSettings(): Settings {
  return {
    apiUrl: getApiUrl(),
    apiKey: getApiKey(),
    theme: (localStorage.getItem("erock_theme") as "light" | "dark") || "light",
  };
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadSettings);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", settings.theme === "dark");
  }, [settings.theme]);

  const value: SettingsContextValue = {
    ...settings,
    setApiUrl: (url) => {
      localStorage.setItem("erock_api_url", url);
      setSettings((s) => ({ ...s, apiUrl: url }));
    },
    setApiKey: (key) => {
      localStorage.setItem("erock_api_key", key);
      setSettings((s) => ({ ...s, apiKey: key }));
    },
    setTheme: (theme) => {
      localStorage.setItem("erock_theme", theme);
      setSettings((s) => ({ ...s, theme }));
    },
  };

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used within SettingsProvider");
  return ctx;
}
