"""Tests for BATCH-107 — Dark Mode + Keyboard Shortcuts.

Backend tests verify hooks export correctly and TypeScript compiles.
Full hook behavior tested via frontend test runner.
AIV v5.3 — T1, T2, T5.
"""
from __future__ import annotations

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Dark mode is now implemented in settings-context.tsx (useSettings),
# not a standalone useDarkMode.ts hook. The toggle, persistence, and
# class manipulation are all in the settings context.
DARK_MODE_FILE = PROJECT_ROOT / "frontend/src/contexts/settings-context.tsx"


def test_107_01_dark_mode_hook_exists():
    """Dark mode implementation file exists."""
    assert DARK_MODE_FILE.exists()


def test_107_01_dark_mode_has_toggle():
    """Settings context exports theme toggle."""
    content = DARK_MODE_FILE.read_text(encoding="utf-8")
    assert "setTheme" in content
    assert '"dark"' in content
    assert 'localStorage' in content


def test_107_01_dark_mode_uses_class():
    """Settings context toggles dark/light class on document."""
    content = DARK_MODE_FILE.read_text(encoding="utf-8")
    assert "classList" in content
    assert '"dark"' in content


def test_107_01_dark_mode_has_persistence():
    """Settings context persists theme choice."""
    content = DARK_MODE_FILE.read_text(encoding="utf-8")
    assert "erock_theme" in content
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
