"""Section-aware text chunker for scientific papers."""

from pydantic import BaseModel


class DocumentChunk(BaseModel):
    """A chunk of text from a parsed document."""
    text: str
    paper_id: str
    section: str = "unknown"
    page_number: int | None = None
    chunk_index: int = 0
    metadata: dict = {}


# Section headers that indicate major boundaries
SECTION_PATTERNS = [
    "abstract", "introduction", "background", "related work", "methodology",
    "methods", "approach", "experiments", "results", "discussion",
    "conclusion", "conclusions", "references", "acknowledgments", "appendix",
]


def chunk_text(
    text: str,
    paper_id: str,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> list[DocumentChunk]:
    """Split text into overlapping chunks, respecting section boundaries when possible."""
    if not text.strip():
        return []

    # Try to split by sections first
    sections = _split_sections(text)
    chunks = []

    for section_name, section_text in sections:
        if not section_text.strip():
            continue

        # If section is short enough, keep it as one chunk
        if len(section_text) <= chunk_size:
            chunks.append(DocumentChunk(
                text=section_text.strip(),
                paper_id=paper_id,
                section=section_name,
                chunk_index=len(chunks),
            ))
        else:
            # Split long sections with overlap
            start = 0
            while start < len(section_text):
                end = start + chunk_size
                chunk_text_part = section_text[start:end]

                # Try to break at sentence boundary
                if end < len(section_text):
                    last_period = chunk_text_part.rfind(". ")
                    if last_period > chunk_size // 2:
                        end = start + last_period + 1
                        chunk_text_part = section_text[start:end]

                chunks.append(DocumentChunk(
                    text=chunk_text_part.strip(),
                    paper_id=paper_id,
                    section=section_name,
                    chunk_index=len(chunks),
                ))
                start = end - overlap if end < len(section_text) else end

    return chunks


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (section_name, section_text) pairs."""
    sections = []
    current_section = "header"
    current_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip().lower()
        is_section = False

        for pattern in SECTION_PATTERNS:
            # Match lines that look like section headers (short, possibly numbered)
            if stripped == pattern or stripped.startswith(pattern) and len(stripped) < 60:
                # Save previous section
                if current_lines:
                    sections.append((current_section, "\n".join(current_lines)))
                current_section = line.strip()
                current_lines = []
                is_section = True
                break

        if not is_section:
            current_lines.append(line)

    # Save last section
    if current_lines:
        sections.append((current_section, "\n".join(current_lines)))

    return sections
