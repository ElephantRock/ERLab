/**
 * BATCH-145: Sidebar Navigation Restructure Tests
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";

const content = fs.readFileSync("src/components/layout/sidebar.tsx", "utf-8");

describe("TEST-145: Sidebar restructure", () => {
  it("TEST-145-01: has 3 groups (Primary, Research Tools, System)", () => {
    expect(content).toContain("label: \"Primary\"");
    expect(content).toContain("label: \"Research Tools\"");
    expect(content).toContain("label: \"System\"");
  });

  it("TEST-145-02: Primary group has 4 items", () => {
    const primarySection = content.substring(
      content.indexOf("label: \"Primary\""),
      content.indexOf("label: \"Research Tools\"")
    );
    const items = primarySection.match(/to: "/g);
    expect(items).toHaveLength(4);
  });

  it("TEST-145-03: Research Tools group has 6 items", () => {
    const researchSection = content.substring(
      content.indexOf("label: \"Research Tools\""),
      content.indexOf("label: \"System\"")
    );
    const items = researchSection.match(/to: "/g);
    expect(items).toHaveLength(6);
  });

  it("TEST-145-04: System group has 6 items", () => {
    const systemSection = content.substring(content.indexOf("label: \"System\""));
    const items = systemSection.match(/to: "/g);
    expect(items).toHaveLength(6);
  });

  it("TEST-145-05: total items = 16 (none lost)", () => {
    const allItems = content.match(/to: "\//g);
    // 16 items in NAV_GROUPS + 0 elsewhere = 16
    expect(allItems!.length).toBeGreaterThanOrEqual(16);
  });

  it("TEST-145-06: has group label headers when not collapsed", () => {
    expect(content).toContain("uppercase tracking-wider");
    expect(content).toContain("text-muted-foreground/60");
  });

  it("TEST-145-07: has visual dividers when collapsed", () => {
    expect(content).toContain("role=\"separator\"");
  });

  it("TEST-145-08: mobile nav still works with NAV_ITEMS", () => {
    expect(content).toContain("NAV_ITEMS.filter((item) => item.mobile)");
    expect(content).toContain("MobileBottomNav");
  });
});
