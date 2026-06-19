/**
 * Sidebar Navigation Tests — Research Studio Layout
 */
import { describe, it, expect } from "vitest";
import * as fs from "fs";

const content = fs.readFileSync("src/components/layout/sidebar.tsx", "utf-8");

describe("Sidebar — Research Studio Layout", () => {
  it("has 4 groups (Studio, Research, System, Advanced)", () => {
    expect(content).toContain("label: \"Studio\"");
    expect(content).toContain("label: \"Research\"");
    expect(content).toContain("label: \"System\"");
    expect(content).toContain("label: \"Advanced\"");
  });

  it("Studio group has Home, New Run, Results, Review", () => {
    const section = content.substring(
      content.indexOf("label: \"Studio\""),
      content.indexOf("label: \"Research\"")
    );
    expect(section).toContain("label: \"Home\"");
    expect(section).toContain("label: \"New Run\"");
    expect(section).toContain("label: \"Results\"");
    expect(section).toContain("label: \"Review\"");
  });

  it("Research group has Gaps, Literature, Knowledge Graph", () => {
    const section = content.substring(
      content.indexOf("label: \"Research\""),
      content.indexOf("label: \"System\"")
    );
    expect(section).toContain("label: \"Gaps\"");
    expect(section).toContain("label: \"Literature\"");
    expect(section).toContain("label: \"Knowledge Graph\"");
  });

  it("System group has Operations and Settings", () => {
    const section = content.substring(
      content.indexOf("label: \"System\""),
      content.indexOf("label: \"Advanced\"")
    );
    expect(section).toContain("label: \"Operations\"");
    expect(section).toContain("label: \"Settings\"");
  });

  it("Advanced group is collapsed by default", () => {
    expect(content).toContain("collapsedByDefault: true");
  });

  it("Dashboard route is / with label Home", () => {
    const section = content.substring(
      content.indexOf("label: \"Studio\""),
      content.indexOf("label: \"Research\"")
    );
    expect(section).toContain("to: \"/\"");
    expect(section).toContain("label: \"Home\"");
  });

  it("Results maps to /ideas", () => {
    const section = content.substring(
      content.indexOf("label: \"Studio\""),
      content.indexOf("label: \"Research\"")
    );
    expect(section).toContain('to: "/ideas"');
    expect(section).toContain("label: \"Results\"");
  });

  it("Review maps to /governance", () => {
    const section = content.substring(
      content.indexOf("label: \"Studio\""),
      content.indexOf("label: \"Research\"")
    );
    expect(section).toContain('to: "/governance"');
    expect(section).toContain("label: \"Review\"");
  });

  it("has collapsible toggle for Advanced", () => {
    expect(content).toContain("setIsExpanded");
  });

  it("has dark sidebar theme tokens", () => {
    const css = fs.readFileSync("src/globals.css", "utf-8");
    expect(css).toContain("sidebar-bg");
    expect(css).toContain("sidebar-active");
  });

  it("mobile nav still works", () => {
    expect(content).toContain("MOBILE_ITEMS");
    expect(content).toContain("MobileBottomNav");
  });
});
