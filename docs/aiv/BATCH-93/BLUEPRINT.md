BATCH BLUEPRINT — BATCH-93
═══════════════════════════════════════════════════════════
Batch ID: BATCH-93 | Version: 1.0 | Cycle: STANDARD | Lead: ivory-wolf
Date: 2026-05-07 | Sequencing: SEQUENTIAL
───────────────────────────────────────────────────────────
GOAL: MCP (Model Context Protocol) tool integration layer.
Allows pipeline stages to call external tools via a standardized
protocol. Currently supports search, code execution, and file I/O.
───────────────────────────────────────────────────────────
TEST BASELINE: 2,098 | Delta: +8 | Expected: 2,106
───────────────────────────────────────────────────────────
TASK-01: MCP Tool Registry (Critical)
  Files: backend/pipeline/tools/mcp/client.py (NEW)
  Tests: 8 tests
───────────────────────────────────────────────────────────
BAC-01: MCPToolRegistry with register/call/list
BAC-02: Tool isolation — failure in one tool doesn't crash others
BAC-03: Built-in tools: search, code_exec, file_read
BAC-04: CHANGELOG.md updated
HB-01: Tool execution timeout enforced (10s default)
HB-02: Unknown tool returns error, doesn't crash
═══════════════════════════════════════════════════════════
