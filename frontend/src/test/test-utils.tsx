import { render, type RenderOptions } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SettingsProvider } from "@/contexts/settings-context";
import { AuthProvider } from "@/contexts/auth-context";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface TestProvidersProps {
  children: ReactNode;
  initialEntries?: string[];
}

function TestProviders({ children, initialEntries }: TestProvidersProps) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
    <MemoryRouter initialEntries={initialEntries}>
      <SettingsProvider>
        <AuthProvider>{children}</AuthProvider>
      </SettingsProvider>
    </MemoryRouter>
    </QueryClientProvider>
  );
}

interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  initialEntries?: string[];
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderWithProvidersOptions,
) {
  const { initialEntries, ...renderOptions } = options || {};
  return {
    user: userEvent.setup(),
    ...render(ui, {
      wrapper: ({ children }) => (
        <TestProviders initialEntries={initialEntries}>{children}</TestProviders>
      ),
      ...renderOptions,
    }),
  };
}
