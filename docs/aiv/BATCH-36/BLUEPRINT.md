BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID: BATCH-36 | Version: 1.0 | SIMPLIFIED | Lead | 2026-05-02

SIMPLIFIED: 1 Task, no existing source files modified (new files only).

BATCH GOAL: Add react-i18next infrastructure. English as default.

TASK-01: i18n Infrastructure
  Files: frontend/src/i18n/ (NEW — config.ts, en.json)
         frontend/src/components/i18n/language-switcher.tsx (NEW)
         frontend/src/main.tsx (MODIFY — add I18nextProvider)
  Tests: TEST-36-01-01: i18n initializes with English
         TEST-36-01-02: Language switcher renders
         TEST-36-01-03: Translation key resolves to English text
  Commit: feat(batch-36/task-01): add i18n infrastructure with English locale

DEPENDENCY: BATCH-34
BASELINE: ~1,859 | Delta: +3 | Target: ~1,862
BAC: ✓ | Lead Sign: Lead + 2026-05-02 12:35
═══════════════════════════════════════════════════════════
