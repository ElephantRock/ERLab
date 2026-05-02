import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UploadZone } from "@/components/knowledge/upload-zone";
import { ingestPdf } from "@/api/knowledge";

vi.mock("@/api/knowledge", () => ({
  ingestPdf: vi.fn(),
  getKnowledgeStats: vi.fn(),
  searchKnowledge: vi.fn(),
}));

const mockIngestPdf = vi.mocked(ingestPdf);

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function createFile(name: string, content: string, type = "application/pdf"): File {
  return new File([content], name, { type });
}

describe("BATCH-24/TASK-02: UploadZone", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── TEST-24-02-01: Upload zone renders with drop area ──
  it("TEST-24-02-01: renders upload zone with drop area", () => {
    renderWithClient(<UploadZone />);

    expect(screen.getByTestId("upload-zone")).toBeInTheDocument();
    expect(screen.getByTestId("drop-area")).toBeInTheDocument();
    expect(screen.getByText(/drop a pdf here/i)).toBeInTheDocument();
  });

  // ── TEST-24-02-02: Drop PDF triggers ingest API call ──
  it("TEST-24-02-02: dropping a PDF triggers ingestPdf API call", async () => {
    mockIngestPdf.mockResolvedValueOnce({
      status: "ingested",
      filename: "paper.pdf",
      chunks: 12,
    });

    renderWithClient(<UploadZone />);

    const dropArea = screen.getByTestId("drop-area");
    const file = createFile("paper.pdf", "%PDF-1.4 fake content");

    fireEvent.drop(dropArea, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(mockIngestPdf).toHaveBeenCalledWith(file);
    });
  });

  // ── TEST-24-02-03: Non-PDF file shows error ──
  it("TEST-24-02-03: dropping a non-PDF file shows error", async () => {
    renderWithClient(<UploadZone />);

    const dropArea = screen.getByTestId("drop-area");
    const file = createFile("malware.exe", "MZ binary", "application/octet-stream");

    fireEvent.drop(dropArea, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(screen.getByTestId("upload-error")).toBeInTheDocument();
      expect(screen.getByText(/not a pdf/i)).toBeInTheDocument();
    });
    expect(mockIngestPdf).not.toHaveBeenCalled();
  });

  // ── TEST-24-02-05: Upload progress shows loading state ──
  it("TEST-24-02-05: uploading PDF shows loading state", async () => {
    // Keep the promise pending so we can observe the loading state
    let resolveUpload: (value: unknown) => void;
    mockIngestPdf.mockReturnValueOnce(new Promise((resolve) => { resolveUpload = resolve; }));

    renderWithClient(<UploadZone />);

    const dropArea = screen.getByTestId("drop-area");
    const file = createFile("paper.pdf", "%PDF-1.4");

    fireEvent.drop(dropArea, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(screen.getByTestId("upload-loading")).toBeInTheDocument();
      expect(screen.getByText(/uploading/i)).toBeInTheDocument();
    });

    // Resolve to clean up
    resolveUpload!({ status: "ingested", filename: "paper.pdf", chunks: 5 });
    await waitFor(() => {
      expect(screen.getByTestId("upload-success")).toBeInTheDocument();
    });
  });

  // ── TEST-24-02-06: Upload success shows confirmation ──
  it("TEST-24-02-06: successful upload shows confirmation with chunk count", async () => {
    mockIngestPdf.mockResolvedValueOnce({
      status: "ingested",
      filename: "research.pdf",
      chunks: 8,
    });

    renderWithClient(<UploadZone />);

    const dropArea = screen.getByTestId("drop-area");
    const file = createFile("research.pdf", "%PDF-1.4 content");

    fireEvent.drop(dropArea, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(screen.getByTestId("upload-success")).toBeInTheDocument();
      expect(screen.getByText(/successfully ingested research.pdf/i)).toBeInTheDocument();
      expect(screen.getByText(/8 chunks indexed/)).toBeInTheDocument();
    });
  });

  // ── TEST-24-02-04: Stats banner shows document counts (in KnowledgeSearch page context) ──
  it("TEST-24-02-04: upload zone calls onUploadSuccess callback", async () => {
    const onUploadSuccess = vi.fn();
    mockIngestPdf.mockResolvedValueOnce({
      status: "ingested",
      filename: "paper.pdf",
      chunks: 3,
    });

    renderWithClient(<UploadZone onUploadSuccess={onUploadSuccess} />);

    const dropArea = screen.getByTestId("drop-area");
    const file = createFile("paper.pdf", "%PDF-1.4");

    fireEvent.drop(dropArea, {
      dataTransfer: { files: [file] },
    });

    await waitFor(() => {
      expect(onUploadSuccess).toHaveBeenCalledWith({
        filename: "paper.pdf",
        chunks: 3,
      });
    });
  });
});
