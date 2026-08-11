"""Generic document parser — handles PDF, TXT, CSV, DOCX (B160).

Provides a unified parse_and_chunk() interface for all supported
document formats. Falls back gracefully when optional deps are missing.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from backend.pipeline.ingestion.chunker import DocumentChunk, chunk_text

logger = logging.getLogger(__name__)

# Supported file extensions and their MIME types
SUPPORTED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Magic bytes for format validation
_MAGIC_BYTES = {
    b"%PDF": "pdf",
    b"PK": "docx",  # ZIP-based (DOCX, XLSX, etc.)
}


def detect_format(filename: str, data: bytes | None = None) -> str | None:
    """Detect file format from extension and optionally magic bytes."""
    ext = Path(filename).suffix.lower()
    if ext in SUPPORTED_EXTENSIONS:
        return ext.lstrip(".")

    # Fallback: check magic bytes
    if data and len(data) >= 4:
        for magic, fmt in _MAGIC_BYTES.items():
            if data[:len(magic)] == magic:
                if fmt == "docx" and ext == ".docx":
                    return "docx"
                return fmt
    return None


class DocumentParser:
    """Unified parser for multiple document formats.

    Usage:
        parser = DocumentParser()
        chunks = await parser.parse_and_chunk("/path/to/file.pdf", paper_id="my_paper")
    """

    def __init__(self, chunk_size: int = 1000, overlap: int = 200) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def parse_and_chunk(
        self,
        file_path: str,
        paper_id: str,
        filename: str | None = None,
    ) -> list[DocumentChunk]:
        """Parse any supported document and return chunks.

        Args:
            file_path: Path to the file on disk.
            paper_id: Unique ID for the document.
            filename: Original filename (for format detection).

        Returns:
            List of DocumentChunk objects.
        """
        fname = filename or Path(file_path).name
        fmt = detect_format(fname)

        if fmt == "pdf":
            return await self._parse_pdf(file_path, paper_id)
        elif fmt == "txt" or fmt == "md":
            return self._parse_text(file_path, paper_id)
        elif fmt == "csv":
            return self._parse_csv(file_path, paper_id)
        elif fmt == "docx":
            return self._parse_docx(file_path, paper_id)
        else:
            logger.warning("Unsupported format for '%s', attempting text parse", fname)
            try:
                return self._parse_text(file_path, paper_id)
            except Exception as e:
                logger.error("Failed to parse '%s': %s", fname, e)
                return []

    async def _parse_pdf(self, file_path: str, paper_id: str) -> list[DocumentChunk]:
        """Parse PDF using existing PDFService."""
        from backend.pipeline.ingestion.pdf_service import PDFService
        service = PDFService()
        return await service.parse_and_chunk(
            file_path, paper_id,
            chunk_size=self._chunk_size,
            overlap=self._overlap,
        )

    def _parse_text(self, file_path: str, paper_id: str) -> list[DocumentChunk]:
        """Parse plain text or markdown files."""
        path = Path(file_path)
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return []
        return chunk_text(text, paper_id, chunk_size=self._chunk_size, overlap=self._overlap)

    def _parse_csv(self, file_path: str, paper_id: str) -> list[DocumentChunk]:
        """Parse CSV files — extract headers + sample rows as text."""
        path = Path(file_path)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception as e:
            logger.warning("CSV parse failed: %s", e)
            return []

        if not rows:
            return []

        # Convert rows to text representation
        headers = rows[0] if rows else []
        sample_rows = rows[:51]  # Header + 50 data rows
        text_parts = [
            f"CSV Headers: {', '.join(headers)}",
            f"Total rows: {len(rows) - 1}",
            "",
            "Sample data:",
        ]
        for row in sample_rows:
            text_parts.append(", ".join(str(v) for v in row))

        text = "\n".join(text_parts)
        return chunk_text(text, paper_id, chunk_size=self._chunk_size, overlap=self._overlap)

    def _parse_docx(self, file_path: str, paper_id: str) -> list[DocumentChunk]:
        """Parse DOCX files using python-docx."""
        try:
            from docx import Document
        except ImportError:
            logger.warning("python-docx not installed. Cannot parse DOCX files.")
            # Try as ZIP → extract word/document.xml
            return self._parse_docx_fallback(file_path, paper_id)

        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        if not text.strip():
            return []
        return chunk_text(text, paper_id, chunk_size=self._chunk_size, overlap=self._overlap)

    def _parse_docx_fallback(self, file_path: str, paper_id: str) -> list[DocumentChunk]:
        """Fallback DOCX parsing using zipfile + XML extraction."""
        import xml.etree.ElementTree as ET
        import zipfile

        try:
            with zipfile.ZipFile(file_path) as z:
                with z.open("word/document.xml") as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    # Extract text from all <w:t> elements
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                    texts = [elem.text for elem in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
                             if elem.text]
                    text = "\n".join(texts)
                    if not text.strip():
                        return []
                    return chunk_text(text, paper_id, chunk_size=self._chunk_size, overlap=self._overlap)
        except Exception as e:
            logger.warning("DOCX fallback parse failed: %s", e)
            return []
