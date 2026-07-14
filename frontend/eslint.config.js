// ═══════════════════════════════════════════════════════════════════════
// Elephant Rock — ESLint flat config (ESLint 9)
// ═══════════════════════════════════════════════════════════════════════
//
// Two layers:
//   1. Base recommended sets (js, typescript, react-hooks).
//   2. The four INTERFACE_CONTRACT rules (erock/*), shipped as `warn`.
//
// The contract rules are the load-bearing piece. Each rule's `message`
// cites the PRODUCT.md principle it enforces, so a developer who trips
// one sees the WHY, not just the what. They ship as `warn` in Phase 0 —
// they surface the compliance inventory without breaking the build. They
// flip to `error` in Phase 5 once every page complies (the one-way
// ratchet: the contract only tightens).
//
// See: PRODUCT.md, INTERFACE_CONTRACT.md (§4, §3, §1, §5).

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

// ── The four contract rules ───────────────────────────────────────────
// Each is a small, focused rule object. Kept inline (rather than a
// separate plugin package) because there are only four and they're
// specific to this codebase's contract.

const erockRules = {
  rules: {
    // INTERFACE_CONTRACT §4. PRODUCT.md §6 (honesty in state).
    // Forbids raw Tailwind palette colors and arbitrary hex/hsl values.
    // The semantic tokens (success, warning, destructive, banner-*, accent,
    // muted, primary, ...) are the only legal path. The DA-01 sweep missed
    // 6 sites; this rule makes the 7th impossible.
    "no-raw-colors": {
      meta: {
        type: "problem",
        docs: {
          description:
            "Use semantic color tokens (success, warning, destructive, banner-*, accent, ...) not raw Tailwind palette colors or hex/hsl literals.",
        },
        messages: {
          rawPalette:
            "Avoid raw Tailwind color '{{color}}'. Use a semantic token (PRODUCT.md §6: honesty in state; INTERFACE_CONTRACT §4).",
          arbitrary:
            "Avoid arbitrary color value '{{value}}'. Use a semantic token (PRODUCT.md §6; INTERFACE_CONTRACT §4).",
        },
        schema: [],
      },
      create(context) {
        // Raw palette prefixes we forbid. Matches bg-red-500, text-green-600,
        // border-yellow-300, etc. Does NOT match semantic tokens like
        // bg-success, text-destructive, border-border.
        const RAW_PALETTE = /^(bg|text|border|ring|from|to|via|fill|stroke|outline|shadow|divide|accent|decoration)-(red|green|blue|yellow|amber|orange|pink|rose|violet|purple|indigo|cyan|teal|emerald|lime|sky|fuchsia|slate|gray|zinc|neutral|stone)-(?:50|[1-9]00)\b/;
        // Arbitrary value containing hex or hsl().
        const ARBITRARY_COLOR = /(bg|text|border|ring|fill|stroke)-\[(?:#[0-9a-fA-F]{3,8}|hsla?\()/;

        return {
          JSXAttribute(node) {
            if (node.name?.name !== "className") return;
            const value = node.value;
            if (!value || value.type !== "Literal") return;
            const str = String(value.value ?? "");

            for (const cls of str.split(/\s+/)) {
              if (RAW_PALETTE.test(cls)) {
                const m = cls.match(RAW_PALETTE);
                context.report({
                  node,
                  messageId: "rawPalette",
                  data: { color: m ? `${m[1]}-${m[2]}` : cls },
                });
              }
              if (ARBITRARY_COLOR.test(cls)) {
                context.report({
                  node,
                  messageId: "arbitrary",
                  data: { value: cls },
                });
              }
            }
          },
        };
      },
    },

    // INTERFACE_CONTRACT §3. PRODUCT.md §1 (reading is the center).
    // The floor is 11px (text-ui-micro). Nothing in the product is smaller.
    // Today there are text-[8px], text-[9px], text-[10px] sites (stage
    // timers, micro-badges) — this rule flags them so the reading surface
    // remains the calibrator.
    "no-sub-micro-type": {
      meta: {
        type: "problem",
        docs: {
          description:
            "No text below the ui-micro floor (11px). Use .text-ui-micro or larger.",
        },
        messages: {
          submicro:
            "Type size {{size}} is below the 11px floor. Use .text-ui-micro (11px) or a larger ui/prose scale token (PRODUCT.md §1; INTERFACE_CONTRACT §3).",
        },
        schema: [],
      },
      create(context) {
        const SUBMICRO = /text-\[(\d(?:\.\d+)?)px\]/;
        return {
          JSXAttribute(node) {
            if (node.name?.name !== "className") return;
            const value = node.value;
            if (!value || value.type !== "Literal") return;
            const str = String(value.value ?? "");
            for (const cls of str.split(/\s+/)) {
              const m = cls.match(SUBMICRO);
              if (m && parseFloat(m[1]) < 11) {
                context.report({
                  node,
                  messageId: "submicro",
                  data: { size: `${m[1]}px` },
                });
              }
            }
          },
        };
      },
    },

    // INTERFACE_CONTRACT §1. PRODUCT.md §6 (honesty in state).
    // The defining rule. Fetching must go through useResource; hand-rolled
    // useEffect+fetch is the root cause of the silent-error-swallow
    // pattern and missing caching. Detects fetch/API calls inside
    // useEffect bodies.
    "no-raw-use-effect-fetch": {
      meta: {
        type: "problem",
        docs: {
          description:
            "Fetching inside useEffect is forbidden. Use useResource (INTERFACE_CONTRACT §1).",
        },
        messages: {
          rawFetch:
            "Fetching inside useEffect bypasses the data contract (no caching, no retry, errors can be swallowed). Use useResource (PRODUCT.md §6; INTERFACE_CONTRACT §1).",
        },
        schema: [],
      },
      create(context) {
        // Track depth in useEffect callbacks.
        let inEffect = 0;

        function isFetchLike(callee) {
          if (!callee) return false;
          // Direct call: fetch(...), apiFetch(...)
          if (callee.type === "Identifier") {
            return /^(fetch|apiFetch|apiFetchBlob|apiFetchFormData)$/.test(callee.name);
          }
          // Member call: something.listIdeas(...), client.get(...)
          if (callee.type === "MemberExpression") {
            const apiModules = /^(api|client|ideas|gaps|pipeline|governance|memory|costs|knowledge|literature|status|sessions|autonomous|search|traces|notifications|experiments|ops|knowledgeGraph|exports|collaboration)$/;
            // Heuristic: any *.list*/get*/fetch* call is treated as a fetch.
            const prop = callee.property;
            if (prop.type === "Identifier" && /^(list|get|fetch|search|find|load|trigger|create|approve|deny|update|delete)/.test(prop.name)) {
              // Only flag if the object looks like an api module.
              if (callee.object?.type === "Identifier" && apiModules.test(callee.object.name)) {
                return true;
              }
            }
          }
          return false;
        }

        return {
          CallExpression(node) {
            if (inEffect > 0 && isFetchLike(node.callee)) {
              context.report({ node, messageId: "rawFetch" });
            }
            // Detect useEffect(... ) entry.
            if (
              node.callee?.type === "Identifier" &&
              node.callee.name === "useEffect"
            ) {
              inEffect += 1;
            }
          },
          "CallExpression:exit"(node) {
            if (
              node.callee?.type === "Identifier" &&
              node.callee.name === "useEffect"
            ) {
              inEffect -= 1;
            }
          },
        };
      },
    },

    // INTERFACE_CONTRACT §3. PRODUCT.md §1 (reading is the center).
    // Forbids the telemetry-header pattern: font-mono + uppercase +
    // tracking-widest combined, which is an SRE/dashboard aesthetic
    // inappropriate for research section headings. Survives in genuine
    // data/table contexts (traces, ops) where it belongs.
    "no-telemetry-headings": {
      meta: {
        type: "problem",
        docs: {
          description:
            "The font-mono + uppercase + tracking-widest telemetry pattern is reserved for tabular data, not section headings.",
        },
        messages: {
          telemetry:
            "The font-mono uppercase tracking-widest pattern reads as telemetry, not a research heading. Use a sentence-case ui-heading instead (PRODUCT.md §1; INTERFACE_CONTRACT §3).",
        },
        schema: [],
      },
      create(context) {
        return {
          JSXAttribute(node) {
            if (node.name?.name !== "className") return;
            const value = node.value;
            if (!value || value.type !== "Literal") return;
            const str = String(value.value ?? "");
            const isMono = /\bfont-mono\b/.test(str);
            const isUpper = /\buppercase\b/.test(str);
            const isWidest = /\btracking-widest\b/.test(str) || /\btracking-wider\b/.test(str);
            if (isMono && isUpper && isWidest) {
              context.report({ node, messageId: "telemetry" });
            }
          },
        };
      },
    },
  },
};

// ── The flat config ───────────────────────────────────────────────────

export default tseslint.config(
  // Global ignores.
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "src/**/*.d.ts",
      "scripts/**", // tooling (lint-budget guard, etc.), not product code
      "*.config.js",
      "vite.config.ts",
      "vitest.config.ts",
      "tailwind.config.js",
      "postcss.config.js",
    ],
  },

  // Base JS recommended.
  js.configs.recommended,

  // TypeScript recommended (type-aware rules off for speed; can enable later).
  ...tseslint.configs.recommended,

  // React + React Hooks.
  {
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Phase 0: demote exhaustive-deps to warn. The codebase has 2
      // pre-existing intentional `tick` dependencies used as refresh
      // nudges; forcing their removal is behavioral churn, out of scope
      // for Phase 0. Re-elevate during a focused cleanup pass.
      "react-hooks/exhaustive-deps": "warn",
    },
  },

  // TypeScript recommended — Phase 0 demotions.
  // The recommended set surfaces ~130 pre-existing issues (mostly unused
  // vars/imports) that were never caught because eslint was broken.
  // Phase 0 is pure addition with no behavioral change; fixing those is
  // separate cleanup work. Demote the noisy categories to warn so the
  // build stays green while keeping them visible. Re-elevate after the
  // unused-symbol cleanup pass.
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-unused-vars": "warn",
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-empty-object-type": "warn",
      "@typescript-eslint/no-require-imports": "warn",
      // Phase 0: demote style nits that surfaced as errors once eslint was
      // stood up. They're real but out of scope for "pure addition, no
      // behavioral change". Re-elevate during the cleanup pass.
      "prefer-const": "warn",
      "no-undef": "off", // TypeScript already handles this; avoids false positives.
    },
  },

  // The four contract rules, applied to all .ts/.tsx under src.
  // Phase 5: contract rules flipped from `warn` to `error`.
  // The contract violations reached 0 across the entire codebase, so the
  // ratchet locks. A new page that uses bg-red-500 or a fresh useEffect
  // fetch now gets a build error, not a warning.
  {
    files: ["src/**/*.{ts,tsx}"],
    plugins: { erock: erockRules },
    rules: {
      "erock/no-raw-colors": "error",
      "erock/no-sub-micro-type": "error",
      "erock/no-raw-use-effect-fetch": "error",
      "erock/no-telemetry-headings": "error",
    },
  },

  // Test files: relax the fetch rule (tests legitimately mock fetches and
  // often hand-roll effects). Keep the other three contract rules —
  // tests should still use tokens and the type scale.
  {
    files: ["src/**/*.test.{ts,tsx}", "src/test/**"],
    rules: {
      "erock/no-raw-use-effect-fetch": "off",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
);
