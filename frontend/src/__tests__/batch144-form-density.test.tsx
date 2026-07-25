/**
 * BATCH-144: Pipeline Config Form Density Reduction Tests
 * Verifies essential fields visible, advanced fields hidden by default
 */
import { describe, it, expect } from "vitest";
import { fs } from "fs";

// Read the source file for structural assertions
const fsModule = await import("fs");
const content = fsModule.default.readFileSync("src/components/pipeline/run-config-form.tsx", "utf-8");

describe("TEST-144: Form density reduction", () => {
  it("TEST-144-01: domain input is at top-level (not inside advanced)", () => {
    // Domain should appear BEFORE the advanced-toggle
    const domainIdx = content.indexOf('data-testid="domain-input"');
    const advancedIdx = content.indexOf('data-testid="advanced-toggle"');
    expect(domainIdx).toBeGreaterThan(0);
    expect(advancedIdx).toBeGreaterThan(0);
    expect(domainIdx).toBeLessThan(advancedIdx);
  });

  it("TEST-144-02: strategy select is at top-level (not inside advanced)", () => {
    const strategyIdx = content.indexOf('data-testid="strategy-select"');
    const advancedIdx = content.indexOf('data-testid="advanced-toggle"');
    expect(strategyIdx).toBeGreaterThan(0);
    expect(strategyIdx).toBeLessThan(advancedIdx);
  });

  it("TEST-144-03: max-gaps input is inside advanced-content", () => {
    const maxGapsIdx = content.indexOf('data-testid="max-gaps-input"');
    const advancedContentIdx = content.indexOf('data-testid="advanced-content"');
    expect(maxGapsIdx).toBeGreaterThan(advancedContentIdx);
  });

  it("TEST-144-04: export-format select is inside advanced-content", () => {
    const exportIdx = content.indexOf('data-testid="export-format-select"');
    const advancedContentIdx = content.indexOf('data-testid="advanced-content"');
    expect(exportIdx).toBeGreaterThan(advancedContentIdx);
  });

  it("TEST-144-05: search-queries input is inside advanced-content", () => {
    const searchIdx = content.indexOf('data-testid="search-queries-input"');
    const advancedContentIdx = content.indexOf('data-testid="advanced-content"');
    expect(searchIdx).toBeGreaterThan(advancedContentIdx);
  });

  it("TEST-144-06: exactly 3 primary fields before advanced toggle", () => {
    // Count data-testid inputs before advanced-toggle that are NOT advanced-related.
    // Phase 1 1B raised this from 2 to 3: research-question is now the primary
    // input, with domain (optional context) and strategy. The form-density
    // invariant is preserved at the new intended count.
    const advancedToggleIdx = content.indexOf('data-testid="advanced-toggle"');
    const beforeAdvanced = content.substring(0, advancedToggleIdx);
    const fieldTestIds = beforeAdvanced.match(/data-testid="[^"]*-input"|data-testid="[^"]*-select"/g);
    expect(fieldTestIds).toHaveLength(3);
    expect(fieldTestIds).toContain('data-testid="research-question-input"');
    expect(fieldTestIds).toContain('data-testid="domain-input"');
    expect(fieldTestIds).toContain('data-testid="strategy-select"');
  });

  it("TEST-144-07: default strategy is fast_scan", () => {
    expect(content).toContain('useState<string>("fast_scan")');
  });

  it("TEST-144-08: advanced section has aria-expanded", () => {
    expect(content).toContain("aria-expanded={advancedOpen}");
  });
});
