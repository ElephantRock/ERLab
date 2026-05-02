import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import i18n from "@/i18n/config";
import { LanguageSwitcher } from "@/components/i18n/language-switcher";

// ── TEST-36-01-01: i18n initializes with English ──────────────────

describe("i18n initialization", () => {
  beforeAll(async () => {
    await i18n.init();
  });

  it("TEST-36-01-01: initializes with English as default language", () => {
    expect(i18n.language).toBe("en");
  });

  it("resolves a nav translation key to English text", () => {
    expect(i18n.t("nav.dashboard")).toBe("Dashboard");
    expect(i18n.t("nav.ideas")).toBe("Ideas");
    expect(i18n.t("nav.settings")).toBe("Settings");
  });

  it("resolves common labels to English text", () => {
    expect(i18n.t("common.loading")).toBe("Loading...");
    expect(i18n.t("common.appName")).toBe("Elephant Rock");
  });
});

// ── TEST-36-01-02: Language switcher renders ──────────────────────

describe("LanguageSwitcher", () => {
  it("TEST-36-01-02: renders language switcher with select element", () => {
    render(
      <I18nextProvider i18n={i18n}>
        <LanguageSwitcher />
      </I18nextProvider>,
    );

    const select = screen.getByRole("combobox", { name: /language/i });
    expect(select).toBeInTheDocument();
    expect(select).toHaveValue("en");

    // Should show English as the option
    expect(screen.getByText("English")).toBeInTheDocument();
  });
});

// ── TEST-36-01-03: Translation key resolves to English text ───────

describe("Translation key resolution", () => {
  it("TEST-36-01-03: all nav keys resolve to English strings", () => {
    const navKeys = [
      "dashboard", "pipeline", "ideas", "gaps", "knowledge", "settings",
      "costs", "memory", "governance", "traces", "sessions", "literature",
      "graph", "autonomous", "plugins",
    ];

    for (const key of navKeys) {
      const value = i18n.t(`nav.${key}`);
      expect(value).not.toBe(`nav.${key}`);
      expect(value.length).toBeGreaterThan(0);
    }
  });
});
