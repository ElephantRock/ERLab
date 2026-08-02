#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const baseURL = process.env.ERLAB_FRONTEND_URL || "http://127.0.0.1:5173";
const evidence = path.resolve(process.env.EVIDENCE_DIR || "evidence/browser");
fs.mkdirSync(evidence, { recursive: true });

const scenarios = [];
function add(name, status, details, classification = "ui") {
  scenarios.push({ name, status, details, classification });
}

async function visit(page, name, route, expectedPath) {
  try {
    const response = await page.goto(baseURL + route, { waitUntil: "networkidle", timeout: 60000 });
    await page.waitForTimeout(1000);
    const current = new URL(page.url()).pathname;
    const body = (await page.locator("body").innerText()).slice(0, 4000);
    const screenshot = path.join(evidence, `${name}.png`);
    await page.screenshot({ path: screenshot, fullPage: true });
    const status = expectedPath ? (current === expectedPath ? "pass" : "fail") : "pass";
    add(name, status, {
      requested_route: route,
      final_path: current,
      expected_path: expectedPath || null,
      http_status: response ? response.status() : null,
      body_excerpt: body,
      screenshot: path.basename(screenshot),
    });
    return { current, body };
  } catch (error) {
    add(name, "error", { route, error: String(error) });
    return null;
  }
}

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
const consoleErrors = [];
const pageErrors = [];
const failedRequests = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => pageErrors.push(String(err)));
page.on("requestfailed", (req) => failedRequests.push({ url: req.url(), error: req.failure()?.errorText || "unknown" }));

await visit(page, "ui_dashboard_dev_auth", "/", "/");
await visit(page, "ui_pipeline_new", "/pipeline/new", "/pipeline/new");
await page.reload({ waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
add("ui_reload_after_route", new URL(page.url()).pathname === "/pipeline/new" ? "pass" : "fail", { final_path: new URL(page.url()).pathname });
await visit(page, "ui_login_route", "/login", "/login");
await visit(page, "ui_unknown_route_redirect", "/definitely-not-a-route", "/");

add(
  "ui_runtime_errors",
  pageErrors.length === 0 ? "pass" : "fail",
  { page_errors: pageErrors, console_errors: consoleErrors.slice(0, 100), failed_requests: failedRequests.slice(0, 100) },
  "ui_runtime",
);

await browser.close();

const summary = Object.fromEntries(["pass", "fail", "error", "skip"].map((s) => [s, scenarios.filter((x) => x.status === s).length]));
const report = {
  baseline_tag: "v1.0.1",
  expected_commit: "56ff0e69ba787232252d5e9612330531db330e0c",
  base_url: baseURL,
  scenarios,
  summary,
};
fs.writeFileSync(path.join(evidence, "browser_report.json"), JSON.stringify(report, null, 2));
const md = [
  "# ERLab v1.0.1 Browser E2E Record",
  "",
  "| Scenario | Status | Classification |",
  "|---|---:|---|",
  ...scenarios.map((s) => `| \`${s.name}\` | **${s.status.toUpperCase()}** | ${s.classification} |`),
  "",
  "## Summary",
  "",
  "```json",
  JSON.stringify(summary, null, 2),
  "```",
  "",
].join("\n");
fs.writeFileSync(path.join(evidence, "browser_report.md"), md);
