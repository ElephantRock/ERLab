/**
 * Sidebar Navigation Tests — Loop-Based IA (Phase 1 rebuild).
 *
 * Tests the new IA derived from PRODUCT.md's Core Loop, replacing the old
 * Studio/Research/System/Advanced structure that mirrored the backend.
 * INTERFACE_CONTRACT.md §5 (cites PRODUCT.md "The Core Loop").
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";

const content = fs.readFileSync("src/components/layout/sidebar.tsx", "utf-8");

describe("Sidebar — Loop-Based IA", () => {
  it("has 5 loop groups + Secondary (not Studio/Research/System/Advanced)", () => {
    expect(content).toContain('label: "Direct"');
    expect(content).toContain('label: "Triage"');
    expect(content).toContain('label: "Read"');
    expect(content).toContain('label: "Refine"');
    expect(content).toContain('label: "Govern"');
    expect(content).toContain('label: "Secondary"');
    // Old groups are gone
    expect(content).not.toContain('label: "Studio"');
    expect(content).not.toContain('label: "Research"');
    expect(content).not.toContain('label: "System"');
    expect(content).not.toContain('label: "Advanced"');
  });

  it("Direct group has New Run and Autonomous", () => {
    const section = content.substring(
      content.indexOf('label: "Direct"'),
      content.indexOf('label: "Triage"'),
    );
    expect(section).toContain('label: "New Run"');
    expect(section).toContain('label: "Autonomous"');
  });

  it("Triage group has Results, Gaps, Literature", () => {
    const section = content.substring(
      content.indexOf('label: "Triage"'),
      content.indexOf('label: "Read"'),
    );
    expect(section).toContain('label: "Results"');
    expect(section).toContain('label: "Gaps"');
    expect(section).toContain('label: "Literature"');
  });

  it("Read group has Knowledge Search (was orphaned — The Orphan Route)", () => {
    const section = content.substring(
      content.indexOf('label: "Read"'),
      content.indexOf('label: "Refine"'),
    );
    expect(section).toContain('label: "Knowledge Search"');
    expect(section).toContain('to: "/knowledge"');
  });

  it("Refine group has Sessions", () => {
    const section = content.substring(
      content.indexOf('label: "Refine"'),
      content.indexOf('label: "Govern"'),
    );
    expect(section).toContain('label: "Sessions"');
  });

  it("Govern group has Review", () => {
    const section = content.substring(
      content.indexOf('label: "Govern"'),
      content.indexOf('label: "Secondary"'),
    );
    expect(section).toContain('label: "Review"');
    expect(section).toContain('to: "/governance"');
  });

  it("Secondary group has power-user surfaces", () => {
    const section = content.substring(content.indexOf('label: "Secondary"'));
    expect(section).toContain('label: "Operations"');
    expect(section).toContain('label: "Settings"');
    expect(section).toContain('label: "Costs"');
    expect(section).toContain('label: "Traces"');
    expect(section).toContain('label: "Memory"');
  });

  it("Secondary is marked as secondary (renders below separator)", () => {
    expect(content).toContain("secondary: true");
  });

  it("exports ALL_NAV_ROUTES for reachability auditing", () => {
    expect(content).toContain("ALL_NAV_ROUTES");
  });

  it("has dark sidebar theme tokens", () => {
    const css = fs.readFileSync("src/globals.css", "utf-8");
    expect(css).toContain("sidebar-bg");
    expect(css).toContain("sidebar-active");
  });

  it("does NOT use telemetry-heading pattern (font-mono uppercase tracking-widest)", () => {
    // The old sidebar used text-[10px] font-bold uppercase tracking-widest font-mono
    // for group headers. The new sidebar uses text-ui-micro uppercase tracking-wider.
    expect(content).not.toContain("text-[10px]");
    expect(content).not.toContain("tracking-widest");
  });
});
