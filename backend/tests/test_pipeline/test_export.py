"""Unit tests for export stage — markdown, latex, and export service."""

import asyncio
from pathlib import Path

import pytest

from backend.pipeline.export.export_service import ExportService
from backend.pipeline.export.latex_exporter import LatexExporter
from backend.pipeline.export.markdown_exporter import MarkdownExporter
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal


def _full_proposal() -> ResearchProposal:
    return ResearchProposal(
        title="Novel approach to research methodology",
        abstract="This paper proposes a novel approach combining multiple techniques",
        introduction="Recent advances have opened new possibilities",
        related_work="Prior work has explored similar directions",
        proposed_method="We propose a hybrid retrieval-generation framework",
        expected_contributions="Improved performance on standard benchmarks",
        evaluation_plan="Comprehensive evaluation on standard benchmarks",
        timeline="12 months",
        references=["Smith et al. 2024. Prior Work. ACL.", "Jones 2023. Earlier Work."],
    )


class TestLatexEscape:
    def test_escapes_special_chars(self):
        assert LatexExporter._escape_latex("&") == r"\&"
        assert LatexExporter._escape_latex("%") == r"\%"
        assert LatexExporter._escape_latex("$") == r"\$"
        assert LatexExporter._escape_latex("#") == r"\#"
        assert LatexExporter._escape_latex("_") == r"\_"
        assert LatexExporter._escape_latex("{") == r"\{"
        assert LatexExporter._escape_latex("}") == r"\}"
        assert LatexExporter._escape_latex("~") == r"\textasciitilde{}"
        assert LatexExporter._escape_latex("^") == r"\^{}"

    def test_no_escape_on_plain_text(self):
        plain = "Hello world 123"
        assert LatexExporter._escape_latex(plain) == plain

    def test_empty_string(self):
        assert LatexExporter._escape_latex("") == ""

    def test_inline_math_preserved(self):
        assert LatexExporter._escape_latex("$E = mc^2$") == "$E = mc^2$"

    def test_display_math_preserved(self):
        text = r"$$\sum_{i=1}^n x_i$$"
        assert LatexExporter._escape_latex(text) == text

    def test_mixed_text_and_math(self):
        text = "The loss is $L = \\frac{1}{n}$ and the rate is 50%."
        result = LatexExporter._escape_latex(text)
        assert "$L = \\frac{1}{n}$" in result
        assert r"\%" in result  # prose % is still escaped
        assert "The loss is " in result


class TestMarkdownExporter:
    def test_renders_all_sections(self):
        proposal = _full_proposal()
        md = MarkdownExporter().export(proposal)
        assert "# Novel approach to research methodology" in md
        assert "## Abstract" in md
        assert "## 1. Introduction" in md
        assert "## 3. Proposed Method" in md
        assert "- Smith et al. 2024. Prior Work. ACL." in md
        assert "- Jones 2023. Earlier Work." in md

    def test_writes_to_file(self, tmp_path):
        proposal = _full_proposal()
        out = str(tmp_path / "test.md")
        MarkdownExporter().export(proposal, output_path=out)
        assert Path(out).exists()
        content = Path(out).read_text(encoding="utf-8")
        assert "## Abstract" in content

    def test_missing_references_defaults_to_empty(self):
        proposal = ResearchProposal(title="X", abstract="A")
        md = MarkdownExporter().export(proposal)
        assert "## References" in md

    def test_dict_references_formatted(self):
        proposal = ResearchProposal(
            title="X",
            abstract="A",
            references=[
                {"authors": "Smith et al.", "year": 2024, "title": "Test Paper", "venue": "ACL", "doi": "10.1234/x"},
                {"authors": "Jones", "year": 2023, "title": "Another Paper"},
            ],
        )
        md = MarkdownExporter().export(proposal)
        assert "Smith et al. (2024)" in md
        assert "DOI: 10.1234/x" in md
        assert "Jones (2023)" in md

    def test_dict_evaluation_plan_formatted(self):
        proposal = ResearchProposal(
            title="X",
            abstract="A",
            evaluation_plan={
                "datasets": ["SQuAD", "NQ"],
                "baselines": ["BM25"],
                "metrics": ["EM", "F1"],
                "ablation_design": "Remove retriever",
                "summary": "Full eval",
            },
        )
        md = MarkdownExporter().export(proposal)
        assert "**Datasets**: SQuAD, NQ" in md
        assert "**Baselines**: BM25" in md
        assert "**Ablation Design**: Remove retriever" in md

    def test_string_evaluation_plan_still_works(self):
        proposal = ResearchProposal(title="X", abstract="A", evaluation_plan="Simple plan")
        md = MarkdownExporter().export(proposal)
        assert "Simple plan" in md


class TestLatexExporter:
    def test_renders_latex_document(self):
        proposal = _full_proposal()
        latex = LatexExporter().export(proposal)
        assert r"\documentclass" in latex
        assert r"\begin{document}" in latex
        assert r"\title{" in latex
        assert r"\section{Introduction}" in latex
        assert r"\end{document}" in latex

    def test_escapes_section_content(self):
        proposal = ResearchProposal(
            title="Test & Research 100% Success",
            abstract="Cost is $50 for a #1 ranked _model_",
        )
        latex = LatexExporter().export(proposal)
        assert r"\&" in latex
        assert r"\%" in latex
        assert r"\$" in latex
        assert r"\#" in latex
        assert r"\_" in latex

    def test_writes_to_file(self, tmp_path):
        proposal = _full_proposal()
        out = str(tmp_path / "test.tex")
        LatexExporter().export(proposal, output_path=out)
        assert Path(out).exists()
        content = Path(out).read_text(encoding="utf-8")
        assert r"\end{document}" in content

    def test_structured_dict_references(self):
        proposal = ResearchProposal(
            title="X",
            abstract="A",
            references=[
                {"authors": "Smith et al.", "year": 2024, "title": "Test Paper", "venue": "ACL"},
                "Plain string ref",
            ],
        )
        latex = LatexExporter().export(proposal)
        assert r"\bibitem" in latex
        assert "Smith et al." in latex
        assert "Plain string ref" in latex

    def test_dict_evaluation_plan(self):
        proposal = ResearchProposal(
            title="X",
            abstract="A",
            evaluation_plan={
                "datasets": ["SQuAD", "Natural Questions"],
                "baselines": ["BM25", "DPR"],
                "metrics": ["EM", "F1"],
                "ablation_design": "Remove retrieval component",
                "summary": "Full evaluation plan",
            },
        )
        latex = LatexExporter().export(proposal)
        assert "SQuAD" in latex
        assert "BM25" in latex
        assert r"\textbf" in latex

    def test_risk_mitigation_section(self):
        proposal = ResearchProposal(
            title="X",
            abstract="A",
            risk_mitigation="We will address data quality by using curated datasets.",
        )
        latex = LatexExporter().export(proposal)
        assert r"\section{Risk Mitigation}" in latex


class TestExportService:
    def test_export_markdown(self, tmp_path):
        proposal = _full_proposal()
        service = ExportService(output_dir=str(tmp_path))
        path = asyncio.run(service.export(proposal, format="markdown"))
        assert path.endswith(".md")
        assert Path(path).exists()

    def test_export_latex(self, tmp_path):
        proposal = _full_proposal()
        service = ExportService(output_dir=str(tmp_path))
        path = asyncio.run(service.export(proposal, format="latex"))
        assert path.endswith(".tex")
        assert Path(path).exists()

    def test_format_aliases(self, tmp_path):
        proposal = _full_proposal()
        service = ExportService(output_dir=str(tmp_path))
        md_path = asyncio.run(service.export(proposal, format="md"))
        assert md_path.endswith(".md")
        tex_path = asyncio.run(service.export(proposal, format="tex"))
        assert tex_path.endswith(".tex")

    def test_unknown_format_raises(self, tmp_path):
        proposal = _full_proposal()
        service = ExportService(output_dir=str(tmp_path))
        with pytest.raises(ValueError, match="Unknown format"):
            asyncio.run(service.export(proposal, format="pdf"))

    def test_auto_generates_slug_path(self, tmp_path):
        proposal = ResearchProposal(title="My Great Proposal")
        service = ExportService(output_dir=str(tmp_path))
        path = asyncio.run(service.export(proposal, format="markdown"))
        assert "my-great-proposal" in Path(path).stem
