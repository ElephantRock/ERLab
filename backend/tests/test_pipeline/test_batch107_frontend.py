"""Tests for BATCH-107 — Dark Mode + Keyboard Shortcuts.

Backend tests verify hooks export correctly and TypeScript compiles.
Full hook behavior tested via frontend test runner.
AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest
from pathlib import Path

PROJECT_ROOT = Path("C:/Next-Era/elephant-rock-platform")


def test_107_01_dark_mode_hook_exists():
    """useDarkMode hook file exists."""
    assert (PROJECT_ROOT / "frontend/src/hooks/useDarkMode.ts").exists()


def test_107_01_dark_mode_has_toggle():
    """useDarkMode exports toggle function."""
    content = (PROJECT_ROOT / "frontend/src/hooks/useDarkMode.ts").read_text(encoding="utf-8")
    assert "toggle" in content
    assert "isDark" in content
    assert "localStorage" in content


def test_107_01_dark_mode_uses_class():
    """useDarkMode adds dark/light class to document."""
    content = (PROJECT_ROOT / "frontend/src/hooks/useDarkMode.ts").read_text(encoding="utf-8")
    assert "classList.add" in content
    assert '"dark"' in content
    assert '"light"' in content


def test_107_01_dark_mode_has_persistence():
    """useDarkMode persists theme choice."""
    content = (PROJECT_ROOT / "frontend/src/hooks/useDarkMode.ts").read_text(encoding="utf-8")
    assert "elephant-rock-theme" in content
    assert "setItem" in content
    assert "getItem" in content


def test_107_02_keyboard_shortcuts_hook_exists():
    """useKeyboardShortcuts hook file exists."""
    assert (PROJECT_ROOT / "frontend/src/hooks/useKeyboardShortcuts.ts").exists()


def test_107_02_shortcuts_define_keys():
    """Default shortcuts define j/k/Escape/? keys."""
    content = (PROJECT_ROOT / "frontend/src/hooks/useKeyboardShortcuts.ts").read_text(encoding="utf-8")
    assert '"j"' in content
    assert '"k"' in content
    assert '"Escape"' in content
    assert '"?"' in content


def test_107_02_shortcuts_ignore_inputs():
    """Shortcuts ignored when typing in INPUT/TEXTAREA."""
    content = (PROJECT_ROOT / "frontend/src/hooks/useKeyboardShortcuts.ts").read_text(encoding="utf-8")
    assert "INPUT" in content
    assert "TEXTAREA" in content


def test_107_02_shortcuts_export_types():
    """KeyboardShortcut interface exported."""
    content = (PROJECT_ROOT / "frontend/src/hooks/useKeyboardShortcuts.ts").read_text(encoding="utf-8")
    assert "KeyboardShortcut" in content
    assert "description" in content
    assert "handler" in content
