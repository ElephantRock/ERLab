import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsProvider } from "./contexts/settings-context";
import { Toaster } from "sonner";
import { ErrorBoundary } from "./components/error-boundary";
import App from "./App";
import "./globals.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <SettingsProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
          <Toaster position="bottom-right" />
        </BrowserRouter>
      </SettingsProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
