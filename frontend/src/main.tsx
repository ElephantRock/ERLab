import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsProvider, useSettings } from "./contexts/settings-context";
import { AuthProvider } from "./contexts/auth-context";
import { Toaster } from "sonner";
import { ErrorBoundary } from "./components/error-boundary";
import { initSentry } from "./lib/sentry";
import App from "./App";
import "./i18n/config";
import "./globals.css";

initSentry();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

/** Toaster needs to be inside SettingsProvider to read the theme. */
function ThemedToaster() {
  const { theme } = useSettings();
  return <Toaster position="bottom-right" theme={theme} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <SettingsProvider>
        <AuthProvider>
          <BrowserRouter>
            <ErrorBoundary>
              <App />
            </ErrorBoundary>
            <ThemedToaster />
          </BrowserRouter>
        </AuthProvider>
      </SettingsProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
