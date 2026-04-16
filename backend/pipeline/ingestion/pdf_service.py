"""PDF parsing service — wraps S1-Parser or falls back to PyMuPDF."""

import logging
from pathlib import Path

from backend.pipeline.ingestion.chunker import DocumentChunk, chunk_text

logger = logging.getLogger(__name__)


class StructuredDocument:
    """Result of PDF parsing."""

    def __init__(self, text: str, pages: list[str] | None = None, metadata: dict | None = None):
        self.text = text
        self.pages = pages or []
        self.metadata = metadata or {}


class PDFService:
    """Parse PDFs into structured text using S1-Parser or PyMuPDF fallback."""

    def __init__(self, mode: str = "import", s1_parser_url: str = "http://localhost:8000"):
        self._mode = mode
        self._s1_url = s1_parser_url

    async def parse_pdf(self, file_path: str) -> StructuredDocument:
        """Parse a PDF file and return structured text."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        if self._mode == "import":
            return self._parse_via_import(file_path)
        else:
            return await self._parse_via_http(file_path)

    async def parse_and_chunk(
        self,
        file_path: str,
        paper_id: str,
        chunk_size: int = 1000,
        overlap: int = 200,
    ) -> list[DocumentChunk]:
        """Parse a PDF and split into chunks for embedding."""
        doc = await self.parse_pdf(file_path)
        return chunk_text(doc.text, paper_id, chunk_size=chunk_size, overlap=overlap)

    def _parse_via_import(self, file_path: str) -> StructuredDocument:
        """Use S1-Parser (magic_pdf) directly."""
        try:
            import fitz  # PyMuPDF as primary fallback
            doc = fitz.open(file_path)
            pages = [page.get_text() for page in doc]
            full_text = "\n\n".join(pages)
            doc.close()
            return StructuredDocument(
                text=full_text,
                pages=pages,
                metadata={"parser": "pymupdf", "page_count": len(pages)},
            )
        except ImportError:
            logger.warning("PyMuPDF not available, trying basic extraction")
            return self._basic_extraction(file_path)

    async def _parse_via_http(self, file_path: str) -> StructuredDocument:
        """Use S1-Parser via HTTP API."""
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(file_path, "rb") as f:
                response = await client.post(
                    f"{self._s1_url}/parse",
                    files={"file": f},
                )
            response.raise_for_status()
            data = response.json()
            return StructuredDocument(
                text=data.get("text", ""),
                pages=data.get("pages", []),
                metadata=data.get("metadata", {}),
            )

    @staticmethod
    def _basic_extraction(file_path: str) -> StructuredDocument:
        """Basic text extraction as last resort."""
        try:
            import pdfplumber

            pages = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages.append(text)
            return StructuredDocument(
                text="\n\n".join(pages),
                pages=pages,
                metadata={"parser": "pdfplumber", "page_count": len(pages)},
            )
        except ImportError:
            # Ultimate fallback: read raw bytes (will be garbage but won't crash)
            logger.error("No PDF parser available. Install PyMuPDF or pdfplumber.")
            return StructuredDocument(text="", metadata={"parser": "none"})
