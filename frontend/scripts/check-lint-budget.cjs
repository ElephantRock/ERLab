// ═══════════════════════════════════════════════════════════════════════
// check-lint-budget.cjs — the warning-budget guard (Wave 0.5D)
// ═══════════════════════════════════════════════════════════════════════
//
// Runs eslint, counts warnings by category, compares against the frozen
// baseline in lint-budget.json, and exits nonzero if the count grew.
//
// The ratchet only works if the baseline cannot silently grow. This script
// is the mechanical enforcement of that — see phase_0_lint_baseline.md.
//
// Two budgets are tracked separately:
//   contract (erock/*)   — MUST reach 0 before Phase 5 flips to errors.
//   hygiene (everything) — real debt, separate schedule, non-blocking.
//
// Usage:
//   npm run lint:budget                      # check against baseline
//   npm run lint:budget -- --update-baseline # write the current count
//                                            # as the new baseline
//                                            # (ONLY if ≤ current baseline)
//
// Exit codes:
//   0 — current ≤ baseline (reductions welcome)
//   1 — current > baseline (regression; CI fails)
//   2 — eslint itself failed to run
//   3 — baseline file missing or malformed

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const BASELINE_PATH = path.join(__dirname, "..", "lint-budget.json");
const UPDATE = process.argv.includes("--update-baseline");

// ── Run eslint, get JSON ──────────────────────────────────────────────

// eslint v9 exposes a programmatic Node API (the ESLint class) that's
// flat-config-aware. Using it avoids spawning a shell and sidesteps the
// Windows .cmd / npx EINVAL issues that plague execFileSync("npx.cmd").
// We spawn a node subprocess that runs the async API and prints JSON,
// keeping the parent script synchronous for simple control flow.
//
// NB: ESLint v9 requires `cwd` to be an ABSOLUTE path.
const ROOT_ABS = path.resolve(__dirname, "..");
let results;
try {
  results = execFileSync(process.execPath, ["-e", `
    const { ESLint } = require("eslint");
    (async () => {
      const eslint = new ESLint({ cwd: process.argv[1] });
      const results = await eslint.lintFiles(["."]);
      process.stdout.write(JSON.stringify(results));
    })().catch(e => { console.error(String(e && e.stack || e)); process.exit(2); });
  `, ROOT_ABS], {
    encoding: "utf8",
    maxBuffer: 50 * 1024 * 1024,
    cwd: ROOT_ABS,
  });
} catch (err) {
  // The subprocess writes its own error to stderr and exits 2; surface both.
  console.error("✗ eslint failed to run:");
  if (err.stderr) console.error(err.stderr.toString());
  else console.error(err.message);
  process.exit(2);
}

try {
  results = JSON.parse(results);
} catch (err) {
  console.error("✗ could not parse eslint JSON output:", err.message);
  process.exit(2);
}

// ── Parse + categorize ────────────────────────────────────────────────

const byRule = {};
let total = 0;
let errors = 0;
for (const file of results) {
  for (const msg of file.messages) {
    if (msg.severity === 2) {
      errors++;
      continue; // errors aren't budget; they fail lint directly
    }
    total++;
    const rule = msg.ruleId || "(builtin)";
    byRule[rule] = (byRule[rule] || 0) + 1;
  }
}

// Errors should never reach here (eslint exits nonzero on them), but if
// they somehow do, surface them loudly — they're not budget concerns.
if (errors > 0) {
  console.error(`✗ ${errors} lint error(s) present — fix before checking budget.`);
  process.exit(1);
}

let contract = 0;
let hygiene = 0;
for (const [rule, count] of Object.entries(byRule)) {
  if (rule.startsWith("erock/")) contract += count;
  else hygiene += count;
}

// ── Load baseline ─────────────────────────────────────────────────────

if (!fs.existsSync(BASELINE_PATH)) {
  console.error("✗ lint-budget.json not found. Run `npm run lint:budget -- --update-baseline` to seed it.");
  process.exit(3);
}

let baseline;
try {
  baseline = JSON.parse(fs.readFileSync(BASELINE_PATH, "utf8"));
} catch (err) {
  console.error("✗ lint-budget.json is malformed:", err.message);
  process.exit(3);
}

// ─ --update-baseline mode ─────────────────────────────────────────────

if (UPDATE) {
  // Safety: refuse to write a LARGER baseline. The ratchet only tightens.
  // A growth must be acknowledged by hand-editing the file with a comment,
  // not by running --update-baseline.
  if (total > baseline.total) {
    console.error("✗ refusing to update baseline: current total (" + total + ") > baseline (" + baseline.total + ").");
    console.error("  The ratchet only tightens. If growth is intentional, hand-edit lint-budget.json");
    console.error("  with a recorded exception (LINT-EXCEPTION comment) — do not use --update-baseline.");
    process.exit(1);
  }
  const updated = {
    _comment: baseline._comment,
    _source: baseline._source,
    contract,
    hygiene,
    total,
    byRule,
    _updated: new Date().toISOString(),
  };
  fs.writeFileSync(BASELINE_PATH, JSON.stringify(updated, null, 2) + "\n");
  const delta = total - baseline.total;
  console.log(`✓ baseline updated: ${baseline.total} → ${total} (${delta <= 0 ? "" : "+"}${delta}).`);
  console.log(`  contract: ${baseline.contract} → ${contract}`);
  console.log(`  hygiene: ${baseline.hygiene} → ${hygiene}`);
  console.log(`  review the diff before committing.`);
  process.exit(0);
}

// ─ Check mode ─────────────────────────────────────────────────────────

function fmt(n) { return String(n).padStart(4); }

const contractDelta = contract - baseline.contract;
const hygieneDelta = hygiene - baseline.hygiene;
const totalDelta = total - baseline.total;

console.log("┌─────────────────────────────────────────────────────────┐");
console.log("│  Lint warning budget                                    │");
console.log("├──────────────────────┬──────────┬──────────┬────────────┤");
console.log("│  Category            │  Budget  │ Current  │  Delta     │");
console.log("├──────────────────────┼──────────┼──────────┼────────────┤");
console.log(`│  contract (erock/*)  │  ${fmt(baseline.contract)}  │  ${fmt(contract)}  │  ${pad(contractDelta)} │`);
console.log(`│  hygiene             │  ${fmt(baseline.hygiene)}  │  ${fmt(hygiene)}  │  ${pad(hygieneDelta)} │`);
console.log(`│  TOTAL               │  ${fmt(baseline.total)}  │  ${fmt(total)}  │  ${pad(totalDelta)} │`);
console.log("└──────────────────────┴──────────┴──────────┴────────────┘");

function pad(d) {
  const s = (d > 0 ? "+" : "") + d;
  return s.padStart(8);
}

let failed = false;
const failures = [];
if (contract > baseline.contract) {
  failures.push(`contract: ${baseline.contract} → ${contract} (+${contractDelta})`);
  failed = true;
}
if (hygiene > baseline.hygiene) {
  failures.push(`hygiene: ${baseline.hygiene} → ${hygiene} (+${hygieneDelta})`);
  failed = true;
}
// Total is implied by the two; check it explicitly as a safety net.
if (total > baseline.total && !failed) {
  failures.push(`total: ${baseline.total} → ${total} (+${totalDelta})`);
  failed = true;
}

if (failed) {
  console.error("");
  console.error("✗ WARNING BUDGET EXCEEDED — " + failures.join(", "));
  console.error("");
  console.error("  The ratchet only tightens. New warnings are not allowed without a recorded");
  console.error("  exception. Either:");
  console.error("    1. Fix the regression, then re-run.");
  console.error("    2. Add a // LINT-EXCEPTION comment citing PRODUCT.md, then hand-edit");
  console.error("       lint-budget.json (do NOT use --update-baseline for growth).");
  console.error("");
  console.error("  Per-rule delta:");
  const allRules = new Set([...Object.keys(baseline.byRule || {}), ...Object.keys(byRule)]);
  for (const rule of [...allRules].sort()) {
    const b = baseline.byRule?.[rule] ?? 0;
    const c = byRule[rule] ?? 0;
    if (c !== b) {
      const d = c - b;
      console.error(`    ${rule}: ${b} → ${c} (${d > 0 ? "+" : ""}${d})`);
    }
  }
  process.exit(1);
}

if (totalDelta < 0) {
  console.log("");
  console.log(`✓ budget holds — ${Math.abs(totalDelta)} warning(s) reduced since baseline. Nice.`);
  console.log(`  Run \`npm run lint:budget -- --update-baseline\` to lock in the reduction.`);
} else if (totalDelta === 0) {
  console.log("");
  console.log("✓ budget holds — no growth.");
} else {
  // totalDelta > 0 but within category budgets (e.g. contract down, hygiene up by less)
  console.log("");
  console.log(`✓ budget holds (category-level). Total moved +${totalDelta} but no category grew.`);
}

process.exit(0);
