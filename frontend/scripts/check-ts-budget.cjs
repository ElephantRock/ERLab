// ═══════════════════════════════════════════════════════════════════════
// check-ts-budget.cjs — the TypeScript error-budget ratchet (F0.5)
// ═══════════════════════════════════════════════════════════════════════
//
// Runs `tsc -b --force`, counts 'error TS' lines, compares against the
// frozen baseline in ts-budget.json, and exits nonzero if the count grew.
//
// This is the F0.5 CI ratchet: the F0 recovery (commit 01f4bb2) drove the
// frontend TS build from 101 errors to 0. The ratchet makes 0 the ceiling
// — any regression (a new error, a weakened tsconfig, a suppressed error
// that later fails) fails CI with a clear message instead of relying on
// `npm run build`'s implicit short-circuit.
//
// The budget is separate from `npm run build` because:
//   - build is binary (green/red) and doesn't say HOW MANY errors
//   - this script counts and reports the delta vs baseline
//   - the baseline can be LOWERED only via --update-baseline (which itself
//     refuses to raise the count), making the ratchet one-way
//
// Usage:
//   npm run ts:budget                        # check against baseline (CI)
//   npm run ts:budget -- --update-baseline   # write current count as new
//                                            # baseline (ONLY if ≤ current)
//
// Exit codes:
//   0 — current ≤ baseline (reductions welcome)
//   1 — current > baseline (regression; CI fails)
//   2 — tsc itself failed to run (infra error)
//   3 — baseline file missing or malformed

const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const BUDGET_FILE = path.join(__dirname, "..", "ts-budget.json");
const FROZEN_AT = "01f4bb2 (F0 recovery: 101 -> 0 errors)";

function runTsc() {
  // Invoke the locally-installed TypeScript directly via node (process.execPath),
  // avoiding `npx` which has Windows .cmd / EINVAL issues under execFileSync.
  // This mirrors the approach in check-lint-budget.cjs.
  const tscBin = path.join(__dirname, "..", "node_modules", "typescript", "bin", "tsc");
  try {
    const output = execFileSync(process.execPath, [tscBin, "-b", "--force"], {
      cwd: path.join(__dirname, ".."),
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    return output;
  } catch (err) {
    // tsc exits nonzero on type errors; the output is in err.stdout.
    if (err && err.stdout) return err.stdout;
    // Genuine infra failure (typescript not installed, tsc crashed, etc.).
    console.error("[ts-budget] ERROR: tsc failed to run.");
    console.error(String(err && err.message ? err.message : err));
    process.exit(2);
  }
}

function countErrors(output) {
  return output
    .split(/\r?\n/)
    .filter((line) => /error TS\d+:/.test(line))
    .length;
}

function errorsByCode(output) {
  const byCode = {};
  for (const line of output.split(/\r?\n/)) {
    const m = line.match(/error (TS\d+):/);
    if (m) byCode[m[1]] = (byCode[m[1]] || 0) + 1;
  }
  return byCode;
}

function loadBaseline() {
  if (!fs.existsSync(BUDGET_FILE)) {
    console.error(`[ts-budget] ERROR: baseline file missing: ${BUDGET_FILE}`);
    console.error("[ts-budget] Run `npm run ts:budget -- --update-baseline` to create it.");
    process.exit(3);
  }
  try {
    const raw = JSON.parse(fs.readFileSync(BUDGET_FILE, "utf8"));
    if (typeof raw.total !== "number" || raw.total < 0) throw new Error("malformed 'total'");
    return raw;
  } catch (e) {
    console.error(`[ts-budget] ERROR: baseline malformed: ${e.message}`);
    process.exit(3);
  }
}

function writeBaseline(total, byCode) {
  const baseline = {
    _comment:
      "TypeScript error baseline (F0.5 ratchet). The guard (scripts/check-ts-budget.cjs) compares against this file. The budget may only DECREASE — run `npm run ts:budget -- --update-baseline` after fixing errors to lower it. Hand-edit only with a TS-EXCEPTION comment explaining why.",
    _frozen_at: FROZEN_AT,
    total,
    byCode,
    _updated: new Date().toISOString(),
  };
  fs.writeFileSync(BUDGET_FILE, JSON.stringify(baseline, null, 2) + "\n");
}

function main() {
  const args = process.argv.slice(2);
  const updateMode = args.includes("--update-baseline");

  const output = runTsc();
  const current = countErrors(output);
  const byCode = errorsByCode(output);

  if (updateMode) {
    const baseline = loadBaseline();
    if (current > baseline.total) {
      console.error(
        `[ts-budget] REFUSING to raise baseline: current ${current} > baseline ${baseline.total}.`
      );
      console.error("[ts-budget] Fix the new errors before updating the baseline.");
      process.exit(1);
    }
    writeBaseline(current, byCode);
    console.log(`[ts-budget] baseline updated: ${baseline.total} -> ${current}`);
    process.exit(0);
  }

  const baseline = loadBaseline();
  if (current > baseline.total) {
    console.error(
      `[ts-budget] REGRESSION: current ${current} errors > baseline ${baseline.total}.`
    );
    console.error("[ts-budget] New errors (tsc output):");
    console.error(output);
    console.error(
      "[ts-budget] Fix the errors, or lower the baseline only if you have a TS-EXCEPTION reason."
    );
    process.exit(1);
  }
  if (current < baseline.total) {
    console.log(
      `[ts-budget] improvement: ${current} errors (baseline ${baseline.total}).`
    );
    console.log(
      "[ts-budget] Run `npm run ts:budget -- --update-baseline` to lock in the reduction."
    );
  } else {
    console.log(`[ts-budget] OK: ${current} errors (matches baseline of ${baseline.total}).`);
  }
}

main();
