/**
 * Typography constants for Elephant Rock front-end.
 *
 * These are documentation constants — import them to avoid hardcoding
 * size/weight values. They are NOT runtime-enforced; they serve as a
 * style guide reference.
 *
 * Hierarchy (AIV BATCH-DA-02):
 *   PAGE_TITLE   — <h1> on every page
 *   SECTION_TITLE — CardTitle default (= text-lg font-semibold)
 *   SUBSECTION   — <h3> or emphasized labels
 *   BODY         — default paragraph text
 *   CAPTION      — metadata, timestamps, hints
 */

export const TYPOGRAPHY = {
  PAGE_TITLE: "text-2xl font-bold tracking-tight",
  SECTION_TITLE: "text-lg font-semibold",
  SUBSECTION: "text-base font-medium",
  BODY: "text-sm",
  CAPTION: "text-xs text-muted-foreground",
} as const;

/** Icon size constants */
export const ICON_SIZES = {
  INLINE: "h-3 w-3",
  DEFAULT: "h-4 w-4",
  CARD_HEADER: "h-5 w-5",
  FEATURE: "h-8 w-8",
} as const;

/** Shadow levels */
export const SHADOWS = {
  RESTING: "shadow-sm",
  ELEVATED: "shadow-md",
  FLOATING: "shadow-xl",
} as const;
