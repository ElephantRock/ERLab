import { describe, it, expect } from "vitest";
import { renderWithProviders } from "@/test/test-utils";
import { FeedbackForm } from "@/components/ideas/feedback-form";

describe("FeedbackForm", () => {
  it("renders star buttons and textarea", () => {
    const { getByText, container } = renderWithProviders(<FeedbackForm ideaId={1} />);
    expect(getByText("Submit Feedback")).toBeInTheDocument();
    expect(container.querySelector("textarea")).toBeInTheDocument();
    // 5 star buttons
    const buttons = container.querySelectorAll("button");
    const starButtons = Array.from(buttons).filter((b) => b.querySelector("svg"));
    expect(starButtons.length).toBeGreaterThanOrEqual(5);
  });

  it("disables submit when no rating selected", () => {
    const { getByText } = renderWithProviders(<FeedbackForm ideaId={1} />);
    expect(getByText("Submit Feedback").closest("button")).toBeDisabled();
  });

  it("shows Select rating placeholder initially", () => {
    const { getByText } = renderWithProviders(<FeedbackForm ideaId={1} />);
    expect(getByText("Select rating")).toBeInTheDocument();
  });

  it("enables submit after clicking a star", async () => {
    const { user, getByText, container } = renderWithProviders(<FeedbackForm ideaId={1} />);
    // Click the 4th star button
    const starButtons = container.querySelectorAll("button");
    await user.click(starButtons[3]);
    expect(getByText("4/5")).toBeInTheDocument();
    expect(getByText("Submit Feedback").closest("button")).not.toBeDisabled();
  });

  it("shows rating after selection", async () => {
    const { user, getByText, container } = renderWithProviders(<FeedbackForm ideaId={1} />);
    const starButtons = container.querySelectorAll("button");
    await user.click(starButtons[4]);
    expect(getByText("5/5")).toBeInTheDocument();
  });
});
