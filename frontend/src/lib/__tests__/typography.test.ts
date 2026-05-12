import { describe, it, expect } from "vitest";
import { TYPOGRAPHY, ICON_SIZES, SHADOWS } from "@/lib/typography";

describe("typography constants", () => {
  it("exports PAGE_TITLE with text-2xl font-bold", () => {
    expect(TYPOGRAPHY.PAGE_TITLE).toContain("text-2xl");
    expect(TYPOGRAPHY.PAGE_TITLE).toContain("font-bold");
  });

  it("exports SECTION_TITLE with text-lg font-semibold", () => {
    expect(TYPOGRAPHY.SECTION_TITLE).toContain("text-lg");
    expect(TYPOGRAPHY.SECTION_TITLE).toContain("font-semibold");
  });

  it("exports BODY as text-sm", () => {
    expect(TYPOGRAPHY.BODY).toBe("text-sm");
  });

  it("exports CAPTION with text-xs", () => {
    expect(TYPOGRAPHY.CAPTION).toContain("text-xs");
  });
});

describe("icon size constants", () => {
  it("has 4 size levels", () => {
    expect(Object.keys(ICON_SIZES)).toHaveLength(4);
  });

  it("DEFAULT is h-4 w-4", () => {
    expect(ICON_SIZES.DEFAULT).toBe("h-4 w-4");
  });
});

describe("shadow constants", () => {
  it("has 3 shadow levels", () => {
    expect(Object.keys(SHADOWS)).toHaveLength(3);
  });
});
