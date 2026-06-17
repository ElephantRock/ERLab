"""Tests for surname extraction utility."""

import pytest
from backend.pipeline.verification.surname_utils import (
    extract_surname,
    build_surname_set,
)
from backend.pipeline.literature.models import Author


class TestExtractSurname:
    """Tests for extract_surname across heterogeneous author name formats."""

    def test_comma_format_surname_first(self):
        """'Smith, John' → 'smith'."""
        assert extract_surname("Smith, John") == "smith"

    def test_comma_format_with_initials(self):
        """'Dwivedi, Yogesh K.' → 'dwivedi'."""
        assert extract_surname("Dwivedi, Yogesh K.") == "dwivedi"

    def test_space_format_given_first(self):
        """'John Smith' → 'smith'."""
        assert extract_surname("John Smith") == "smith"

    def test_chinese_name_surname_first(self):
        """'Liu Wei' → 'liu' (Chinese convention: family name first)."""
        assert extract_surname("Liu Wei") == "liu"

    def test_et_al_suffix(self):
        """'Wang et al.' → 'wang'."""
        assert extract_surname("Wang et al.") == "wang"

    def test_et_al_no_period(self):
        """'Wang et al' → 'wang'."""
        assert extract_surname("Wang et al") == "wang"

    def test_single_name(self):
        assert extract_surname("Smith") == "smith"

    def test_empty_string(self):
        assert extract_surname("") == ""

    def test_none_input(self):
        assert extract_surname(None) == ""

    def test_hyphenated_name(self):
        assert extract_surname("Mary-Jane Watson") == "watson"

    def test_multiple_middle_names(self):
        assert extract_surname("Rao Muhammad Anwer") == "anwer"

    def test_author_object(self):
        """Should use .name attribute from Author Pydantic model."""
        a = Author(name="Liu Wei", id="abc")
        assert extract_surname(a) == "liu"

    def test_author_object_with_comma_name(self):
        a = Author(name="Smith, John")
        assert extract_surname(a) == "smith"

    def test_mixed_case(self):
        assert extract_surname("JOHN SMITH") == "smith"
        assert extract_surname("Smith") == "smith"

    def test_korean_name(self):
        """'Kim Jong' → 'kim' (Korean: family name first)."""
        assert extract_surname("Kim Jong") == "kim"


class TestBuildSurnameSet:
    """Tests for build_surname_set from collections."""

    def test_from_string_list(self):
        surnames = build_surname_set(["Smith, John", "Liu Wei", "Jones"])
        assert surnames == {"smith", "liu", "jones"}

    def test_from_author_objects(self):
        authors = [Author(name="Smith, John"), Author(name="Liu Wei")]
        surnames = build_surname_set(authors)
        assert surnames == {"smith", "liu"}

    def test_mixed_input(self):
        authors = [Author(name="Smith, John"), "Liu Wei", "Jones"]
        surnames = build_surname_set(authors)
        assert surnames == {"smith", "liu", "jones"}

    def test_empty_list(self):
        assert build_surname_set([]) == set()

    def test_handles_none_entries(self):
        surnames = build_surname_set(["Smith", None, ""])
        assert surnames == {"smith"}

    def test_deduplication(self):
        surnames = build_surname_set(["Smith, John", "Smith, Mary", "John Smith"])
        assert surnames == {"smith"}
