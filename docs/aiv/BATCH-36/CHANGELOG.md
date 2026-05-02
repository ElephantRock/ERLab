# BATCH-36 CHANGELOG

## [batch-36/task-01] — 2026-05-02

### Added
- **i18next + react-i18next + i18next-browser-languagedetector** to frontend dependencies
- `frontend/src/i18n/config.ts` — i18next initialization with English default, browser language detection
- `frontend/src/i18n/en.json` — English translation keys (nav, pages, common, language)
- `frontend/src/components/i18n/language-switcher.tsx` — Language dropdown component
- `frontend/src/i18n/__tests__/i18n.test.tsx` — 5 tests (3 BLUEPRINT + 2 extended)

### Changed
- `frontend/src/main.tsx` — Added i18n config import for auto-initialization
- `frontend/package.json` — Added 3 i18n dependencies

### Tests
- 5/5 pass | Full suite: 284/284 pass, 0 regressions
