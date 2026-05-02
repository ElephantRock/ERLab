import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MarkdownRenderer } from "@/components/markdown/markdown-renderer";

describe("MarkdownRenderer", () => {
  // ── TEST-11-02-07: Renders basic markdown ───────────────────────
  it("TEST-11-02-07: renders basic markdown content", () => {
    const content = "# Hello World\n\nThis is **bold** and *italic* text.";

    render(<MarkdownRenderer content={content} />);

    // ReactMarkdown converts markdown to HTML elements
    expect(screen.getByText("Hello World")).toBeInTheDocument();
    expect(screen.getByText("bold")).toBeInTheDocument();
    expect(screen.getByText("italic")).toBeInTheDocument();
  });

  // ── TEST-11-02-08: Sanitizes dangerous HTML ─────────────────────
  it("TEST-11-02-08: sanitizes dangerous HTML (script tags not executed)", () => {
    const content = 'Hello <script>alert("xss")</script> World';

    const { container } = render(<MarkdownRenderer content={content} />);

    // ReactMarkdown strips dangerous HTML by default
    const scripts = container.querySelectorAll("script");
    expect(scripts.length).toBe(0);

    // Text content should still be present
    expect(container.textContent).toContain("Hello");
    expect(container.textContent).toContain("World");
  });

  // ── TEST-11-02-09: Renders code blocks ─────────────────────────
  it("TEST-11-02-09: renders code blocks with language class", () => {
    const content = "```python\nprint('hello')\n```";

    const { container } = render(<MarkdownRenderer content={content} />);

    // ReactMarkdown renders fenced code blocks as <pre><code>
    const codeBlock = container.querySelector("code");
    expect(codeBlock).toBeTruthy();
    expect(codeBlock?.textContent).toContain("print('hello')");
  });
});
