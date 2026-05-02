import { axe, toHaveNoViolations } from "jest-axe";
import { render } from "@testing-library/react";

expect.extend(toHaveNoViolations);

/**
 * Check a rendered component for WCAG 2.1 AA accessibility violations.
 * Usage: await checkA11y(<MyComponent />);
 */
export async function checkA11y(ui: React.ReactElement) {
  const { container } = render(ui);
  const results = await axe(container, {
    rules: {
      // Disable color-contrast in jsdom (no real CSS computed)
      "color-contrast": { enabled: false },
    },
  });
  expect(results).toHaveNoViolations();
}
