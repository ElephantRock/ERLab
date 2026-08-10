"""BATCH-160: Local Document Ingestion — multi-format upload + pipeline integration.

TASK-01: Generic DocumentParser (5 tests)
TASK-02: Extended upload API (4 tests)
TASK-03: Pipeline integration (3 tests)
"""
import asyncio
import os
import tempfile

import pytest

# ─── TASK-01: DocumentParser ────────────────────────────────

class TestDocumentParser:

    def test_01_parse_txt_file(self):
        from backend.pipeline.ingestion.document_parser import DocumentParser
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8")
        tmp.write("This is a test document.\nIt has multiple lines.\n" * 50)
        tmp.close()
        try:
            parser = DocumentParser()
            chunks = asyncio.run(parser.parse_and_chunk(tmp.name, "test_doc", filename="test.txt"))
            assert len(chunks) > 0
            assert "test document" in chunks[0].text
        finally:
            os.unlink(tmp.name)

    def test_02_parse_csv_file(self):
        from backend.pipeline.ingestion.document_parser import DocumentParser
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8")
        tmp.write("name,age,city\nAlice,30,NYC\nBob,25,LA\n")
        tmp.close()
        try:
            parser = DocumentParser()
            chunks = asyncio.run(parser.parse_and_chunk(tmp.name, "test_csv", filename="data.csv"))
            assert len(chunks) > 0
            assert "name" in chunks[0].text or "Alice" in chunks[0].text
        finally:
            os.unlink(tmp.name)

    def test_03_parse_md_file(self):
        from backend.pipeline.ingestion.document_parser import DocumentParser
        tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w", encoding="utf-8")
        tmp.write("# Test Document\n\nSome markdown content here.\n\n## Section\n\nMore text.\n")
        tmp.close()
        try:
            parser = DocumentParser()
            chunks = asyncio.run(parser.parse_and_chunk(tmp.name, "test_md", filename="doc.md"))
            assert len(chunks) > 0
        finally:
            os.unlink(tmp.name)

    def test_04_detect_format(self):
        from backend.pipeline.ingestion.document_parser import detect_format
        assert detect_format("test.pdf") == "pdf"
        assert detect_format("test.txt") == "txt"
        assert detect_format("data.csv") == "csv"
        assert detect_format("readme.md") == "md"
        assert detect_format("paper.docx") == "docx"
        assert detect_format("image.png") is None

    def test_05_empty_file_returns_empty(self):
        from backend.pipeline.ingestion.document_parser import DocumentParser
        tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8")
        tmp.write("")
        tmp.close()
        try:
            parser = DocumentParser()
            chunks = asyncio.run(parser.parse_and_chunk(tmp.name, "empty", filename="empty.txt"))
            assert chunks == []
        finally:
            os.unlink(tmp.name)


# ─── TASK-02: Upload API ─────────────────────────────────────

class TestUploadAPI:

    def test_06_supported_extensions(self):
        from backend.api.routes.knowledge import _ALLOWED_EXTENSIONS
        assert ".pdf" in _ALLOWED_EXTENSIONS
        assert ".txt" in _ALLOWED_EXTENSIONS
        assert ".csv" in _ALLOWED_EXTENSIONS
        assert ".md" in _ALLOWED_EXTENSIONS
        assert ".docx" in _ALLOWED_EXTENSIONS

    def test_07_validate_rejects_bad_extension(self):
        from backend.api.errors import BadRequestError
        from backend.api.routes.knowledge import _validate_upload
        with pytest.raises(BadRequestError):
            _validate_upload("malware.exe", b"binary data")

    def test_08_validate_rejects_oversized(self):
        from backend.api.errors import BadRequestError
        from backend.api.routes.knowledge import _MAX_FILE_SIZE, _validate_upload
        big_data = b"x" * (_MAX_FILE_SIZE + 1)
        with pytest.raises(BadRequestError):
            _validate_upload("big.pdf", big_data)

    def test_09_validate_accepts_valid(self):
        from backend.api.routes.knowledge import _validate_upload
        # Should not raise
        _validate_upload("paper.pdf", b"%PDF-1.4 content")
        _validate_upload("notes.txt", b"Hello world")
        _validate_upload("data.csv", b"a,b,c\n1,2,3")


# ─── TASK-03: Pipeline Integration ───────────────────────────

class TestPipelineIntegration:

    def test_10_document_parser_in_ingestion_package(self):
        from backend.pipeline.ingestion.document_parser import DocumentParser, detect_format
        assert DocumentParser is not None
        assert detect_format is not None

    def test_11_source_is_local_upload(self):
        from backend.pipeline.literature.models import Paper
        paper = Paper(
            id="upload:test_doc",
            source="local_upload",
            title="My Uploaded Paper",
            abstract="Some abstract text",
            authors=[],
        )
        assert paper.source == "local_upload"

    def test_12_documents_endpoint_exists(self):
        from backend.api.routes.knowledge import router
        routes = [r.path for r in router.routes]
        assert "/documents" in routes
