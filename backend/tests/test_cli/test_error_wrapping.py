"""Tests for CLI error handling wrapper."""

import pytest

from backend.cli.main import _run_async


class TestCliErrorWrapping:
    def test_system_exit_passes_through(self):
        """SystemExit from API key validation is not caught."""

        async def _raise():
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            _run_async(_raise())

    def test_keyboard_interrupt_handled(self):
        """KeyboardInterrupt shows 'Interrupted' and exits 130."""
        import typer

        async def _raise():
            raise KeyboardInterrupt()

        with pytest.raises(typer.Exit) as exc_info:
            _run_async(_raise())
        assert exc_info.value.exit_code == 130

    def test_generic_exception_shows_panel(self):
        """Generic exceptions are caught and re-raised as typer.Exit(1)."""
        import typer

        async def _raise():
            raise RuntimeError("test error message")

        with pytest.raises(typer.Exit) as exc_info:
            _run_async(_raise())
        assert exc_info.value.exit_code == 1

    def test_import_error_handled(self):
        """ImportError is caught and re-raised as typer.Exit(1)."""
        import typer

        async def _raise():
            raise ImportError("No module named 'chromadb'")

        with pytest.raises(typer.Exit) as exc_info:
            _run_async(_raise())
        assert exc_info.value.exit_code == 1
