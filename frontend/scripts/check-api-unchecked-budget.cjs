// ═══════════════════════════════════════════════════════════════════════
// check-api-unchecked-budget.cjs — unchecked apiFetchUnchecked caller ratchet
// ═══════════════════════════════════════════════════════════════════════
//
// F1.1b: Counts actual apiFetchUnchecked callers (excluding comments + the
// definition in client.ts), compares against the frozen baseline in
// api-unchecked-budget.json, and exits nonzero if the count grew. Also
// prints remaining caller paths so regressions are immediately visible.
//
// The budget may only DECREASE — new callers must use the contract layer
// (callContract) or apiFetchJson with an explicit decoder.
//
// Usage:
//   npm run api:budget                        # check against baseline (CI)
//   npm run api:budget -- --update-baseline   # write current count as new
//                                            # baseline (ONLY if ≤ current)
//
// Exit codes:
//   0 — current ≤ baseline (reductions welcome)
//   1 — current > baseline (regression; CI fails)
//   2 — scan failed (infra error)
//   3 — baseline file missing or malformed

const fs = require("fs");
const path = require("path");

const SRC_DIR = path.join(__dirname, "..", "src");
const BUDGET_FILE = path.join(__dirname, "..", "api-unchecked-budget.json");

function scanCallers(dir) {
  const callers = [];
  function walk(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const fullPath = path.join(d, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === "node_modules" || entry.name === "__tests__") continue;
        walk(fullPath);
      } else if (entry.isFile() && (entry.name.endsWith(".ts") || entry.name.endsWith(".tsx"))) {
        const relPath = path.relative(path.join(__dirname, ".."), fullPath).replace(/\\/g, "/");
        const text = fs.readFileSync(fullPath, "utf8");
        let count = 0;
        for (const line of text.split(/\r?\n/)) {
          const stripped = line.trimStart();
          if (stripped.startsWith("//") || stripped.startsWith("*") || stripped.startsWith("/*")) continue;
          if (line.includes("export async function apiFetchUnchecked")) continue;
          if (/apiFetchUnchecked[<(]/.test(line)) count++;
        }
        if (count > 0) callers.push({ file: relPath, count });
      }
    }
  }
  walk(dir);
  return callers.sort((a, b) => a.file.localeCompare(b.file));
}

function loadBaseline() {
  if (!fs.existsSync(BUDGET_FILE)) {
    console.error(`[api-budget] ERROR: baseline file missing: ${BUDGET_FILE}`);
    process.exit(3);
  }
  try {
    const raw = JSON.parse(fs.readFileSync(BUDGET_FILE, "utf8"));
    if (typeof raw.total_callers !== "number") throw new Error("malformed 'total_callers'");
    return raw;
  } catch (e) {
    console.error(`[api-budget] ERROR: baseline malformed: ${e.message}`);
    process.exit(3);
  }
}

function writeBaseline(callers) {
  const total = callers.reduce((s, c) => s + c.count, 0);
  const baseline = {
    _comment: "Unchecked apiFetchUnchecked<T> caller budget (F1.1b ratchet). The guard (scripts/check-api-unchecked-budget.cjs) compares against this file. The budget may only DECREASE — migrate callers to the contract layer (callContract) or apiFetchJson with a decoder.",
    _frozen_at: "a27fd77 (F1.1a seal)",
    total_callers: total,
    caller_files: callers.length,
    callers,
    _updated: new Date().toISOString(),
  };
  fs.writeFileSync(BUDGET_FILE, JSON.stringify(baseline, null, 2) + "\n");
}

const args = process.argv.slice(2);
const updateMode = args.includes("--update-baseline");

const callers = scanCallers(SRC_DIR);
const current = callers.reduce((s, c) => s + c.count, 0);

if (updateMode) {
  const baseline = loadBaseline();
  if (current > baseline.total_callers) {
    console.error(`[api-budget] REFUSING to raise baseline: current ${current} > baseline ${baseline.total_callers}.`);
    process.exit(1);
  }
  writeBaseline(callers);
  console.log(`[api-budget] baseline updated: ${baseline.total_callers} -> ${current}`);
  process.exit(0);
}

const baseline = loadBaseline();
if (current > baseline.total_callers) {
  console.error(`[api-budget] REGRESSION: current ${current} callers > baseline ${baseline.total_callers}.`);
  console.error("[api-budget] New/changed callers:");
  for (const c of callers) {
    const prev = baseline.callers?.find((b) => b.file === c.file);
    const prevCount = prev ? prev.count : 0;
    if (c.count > prevCount) {
      console.error(`  ${c.file}: ${prevCount} -> ${c.count}`);
    }
  }
  console.error("[api-budget] Migrate new callers to the contract layer or apiFetchJson with a decoder.");
  process.exit(1);
}

if (current < baseline.total_callers) {
  console.log(`[api-budget] improvement: ${current} callers (baseline ${baseline.total_callers}).`);
  console.log("[api-budget] Run `npm run api:budget -- --update-baseline` to lock in the reduction.");
} else {
  console.log(`[api-budget] OK: ${current} unchecked callers (matches baseline of ${baseline.total_callers}).`);
}
