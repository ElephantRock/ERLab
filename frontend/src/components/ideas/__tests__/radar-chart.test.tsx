import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { RadarChart } from "@/components/ideas/radar-chart";

const fiveDimensions = [
  { label: "Novelty", value: 0.8 },
  { label: "Feasibility", value: 0.7 },
  { label: "Completeness", value: 0.6 },
  { label: "Rigor", value: 0.9 },
  { label: "Clarity", value: 0.75 },
];

describe("RadarChart", () => {
  it("renders SVG element", () => {
    const { container } = render(<RadarChart data={fiveDimensions} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.getAttribute("data-testid")).toBe("radar-chart");
  });

  it("renders 5 dimension labels", () => {
    const { container } = render(<RadarChart data={fiveDimensions} />);
    for (const dim of fiveDimensions) {
      const labels = Array.from(container.querySelectorAll("text"));
      const match = labels.find((el) => el.textContent === dim.label);
      expect(match).toBeDefined();
    }
  });

  it("renders polygon with correct points", () => {
    const { container } = render(<RadarChart data={fiveDimensions} size={200} />);
    const polygon = container.querySelector('polygon[data-testid="radar-polygon"]');
    expect(polygon).toBeInTheDocument();

    const pointsStr = polygon?.getAttribute("points") || "";
    const points = pointsStr.split(" ").map((p) => {
      const [x, y] = p.split(",").map(Number);
      return { x, y };
    });

    // 5 data points for 5 dimensions
    expect(points.length).toBe(5);

    // First point (Novelty=0.8) should be near top center
    // center = 100, radius = 70, angle = -PI/2 => (100, 100 - 70*0.8) = (100, 44)
    expect(points[0].x).toBeCloseTo(100, 0);
    expect(points[0].y).toBeCloseTo(44, 0);
  });

  it("applies red color class for low scores", () => {
    const lowData = [
      { label: "A", value: 0.2 },
      { label: "B", value: 0.3 },
      { label: "C", value: 0.1 },
      { label: "D", value: 0.25 },
      { label: "E", value: 0.15 },
    ];
    const { container } = render(<RadarChart data={lowData} />);
    const svg = container.querySelector("svg");
    expect(svg?.classList.contains("radar-color-red")).toBe(true);
  });

  it("applies green color class for high scores", () => {
    const highData = [
      { label: "A", value: 0.9 },
      { label: "B", value: 0.85 },
      { label: "C", value: 0.88 },
      { label: "D", value: 0.92 },
      { label: "E", value: 0.87 },
    ];
    const { container } = render(<RadarChart data={highData} />);
    const svg = container.querySelector("svg");
    expect(svg?.classList.contains("radar-color-green")).toBe(true);
  });
});
