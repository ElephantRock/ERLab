/**
 * BATCH-145: Sidebar Navigation Restructure Tests
 *
 * Updated for Command Center sidebar with 4 groups:
 * Command Center, Research, System, Advanced (collapsed by default)
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";

const content = fs.readFileSync("src/components/layout/sidebar.tsx", "utf-8");

describe("TEST-145: Sidebar restructure", () => {
  it("TEST-145-01: has 4 groups (Command Center, Research, System, Advanced)", () => {
    expect(content).toContain("label: \"Command Center\"");
    expect(content).toContain("label: \"Research\"");
    expect(content).toContain("label: \"System\"");
    expect(content).toContain("label: \"Advanced\"");
  });

  it("TEST-145-02: Command Center group has 4 items", () => {
    const section = content.substring(
      content.indexOf("label: \"Command Center\""),
      content.indexOf("label: \"Research\"")
    );
    const items = section.match(/to: "/g);
    expect(items).toHaveLength(4);
  });

  it("TEST-145-03: Research group has 3 items", () => {
    const section = content.substring(
      content.indexOf("label: \"Research\""),
      content.indexOf("label: \"System\"")
    );
    const items = section.match(/to: "/g);
    expect(items).toHaveLength(3);
  });

  it("TEST-145-04: System group has 4 items", () => {
    const section = content.substring(
      content.indexOf("label: \"System\""),
      content.indexOf("label: \"Advanced\"")
    );
    const items = section.match(/to: "/g);
    expect(items).toHaveLength(4);
  });

  it("TEST-145-05: Advanced group has 5 items", () => {
    const section = content.substring(content.indexOf("label: \"Advanced\""));
    const items = section.match(/to: "\//g);
    expect(items).toHaveLength(5);
  });

  it("TEST-145-06: total items = 16 (none lost)", () => {
    const allItems = content.match(/to: "\//g);
    expect(allItems!.length).toBeGreaterThanOrEqual(16);
  });

  it("TEST-145-07: Advanced group is collapsed by default", () => {
    expect(content).toContain("collapsedByDefault: true");
  });

  it("TEST-145-08: has collapsible toggle for Advanced", () => {
    expect(content).toContain("ChevronDown");
    expect(content).toContain("setIsExpanded");
  });

  it("TEST-145-09: has group label headers when not collapsed", () => {
    expect(content).toContain("uppercase tracking-wider");
    expect(content).toContain("text-muted-foreground/60");
  });

  it("TEST-145-10: has visual dividers when collapsed", () => {
    expect(content).toContain("role=\"separator\"");
  });

  it("TEST-145-11: mobile nav still works with NAV_ITEMS", () => {
    expect(content).toContain("NAV_ITEMS.filter((item) => item.mobile)");
    expect(content).toContain("MobileBottomNav");
  });

  it("TEST-145-12: Settings is in System, not Advanced", () => {
    const systemSection = content.substring(
      content.indexOf("label: \"System\""),
      content.indexOf("label: \"Advanced\"")
    );
    expect(systemSection).toContain("label: \"Settings\"");
  });
});
