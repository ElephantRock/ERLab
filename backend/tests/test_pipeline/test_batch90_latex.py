"""Tests for BATCH-90 — Markdown to LaTeX Converter.

AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest

from backend.pipeline.export.md_to_latex import MarkdownToLatexConverter


@pytest.fixture
def converter():
    return MarkdownToLatexConverter()


def test_90_01_heading_to_section(converter):
    """## Heading → \\subsection{Heading}"""
    result = converter.convert("## Introduction\nSome text.")
    assert "\\subsection{Introduction}" in result


def test_90_01_bold_to_textbf(converter):
    """**bold** → \\textbf{bold}"""
    result = converter.convert("This is **important** text.")
    assert "\\textbf{important}" in result


def test_90_01_italic_to_textit(converter):
    """*italic* → \\textit{italic}"""
    result = converter.convert("This is *emphasized* text.")
    assert "\\textit{emphasized}" in result


def test_90_01_unordered_list(converter):
    """- item → \\begin{itemize} \\item item"""
    result = converter.convert("- First item\n- Second item")
    assert "\\begin{itemize}" in result
    assert "\\item First item" in result
    assert "\\end{itemize}" in result


def test_90_01_ordered_list(converter):
    """1. item → \\begin{enumerate} \\item item"""
    result = converter.convert("1. First\n2. Second")
    assert "\\begin{enumerate}" in result
    assert "\\item First" in result
    assert "\\end{enumerate}" in result


def test_90_01_code_block(converter):
    """```python code ``` → \\begin{verbatim}"""
    result = converter.convert("```python\nprint('hello')\n```")
    assert "\\begin{verbatim}" in result
    assert "print('hello')" in result
    assert "\\end{verbatim}" in result


def test_90_01_convert_to_document(converter):
    """convert_to_document produces complete LaTeX document."""
    result = converter.convert_to_document("# Test\nHello", title="My Paper")
    assert "\\documentclass" in result
    assert "\\title{My Paper}" in result
    assert "\\section{Test}" in result
    assert "Hello" in result
    assert "\\end{document}" in result


def test_90_01_empty_input(converter):
    """Empty input returns empty string."""
    assert converter.convert("") == ""
