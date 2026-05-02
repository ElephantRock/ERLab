# BATCH-50 INLINE REVIEW REPORT

**Reviewer:** Lead Agent (inline review per §6.3)  
**Date:** 2026-05-02

## Verdict: APPROVED_WITH_NOTES

### CHK-01: File References — PASS
- `frontend/src/i18n/en.json` — EXISTS, 4 sections (nav, pages, common, language), ~55 keys
- `frontend/src/i18n/config.ts` — EXISTS, currently registers only `en`
- `frontend/src/components/i18n/language-switcher.tsx` — EXISTS, currently 1 language
- No WebSocket files exist — confirmed, all new

### CHK-02: Data Model — PASS
- Translation structure is flat nested JSON (nav.*, pages.*, common.*, language.*)
- zh.json and es.json must have identical structure to en.json

### CHK-03: Code Patterns — PASS
- LanguageSwitcher uses `SUPPORTED_LANGUAGES` const array — just add 2 entries
- i18next config uses static imports — add zh/es imports
- No existing WebSocket code — clean slate

### CHK-04: Scope — PASS with note
- en.json only has ~55 keys — translation is small and achievable
- WebSocket is backend-only + 1 frontend hook — well-scoped

### CHK-05: Dependencies — PASS
- TASK-01 and TASK-02 are fully independent

### CHK-06: Tests — PASS
- 3 translation tests + 6 WebSocket tests = 9 total — sufficient

## Notes for Assistant
1. en.json has exactly 4 top-level keys with nested values — zh.json and es.json must mirror this exactly
2. language section should add `"zh": "中文"` and `"es": "Español"` keys
3. WebSocket is not yet in the FastAPI app — register as `app.websocket_route()` or use `APIRouter.websocket()`
4. `useWebSocket` must handle ws:// vs wss:// based on window.location.protocol

*INLINE REVIEW — BATCH-50 — AIV Framework v5.1*
