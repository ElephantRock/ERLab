#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const evidenceDir = process.env.EVIDENCE_DIR || path.resolve("evidence/live-paper");
const frontendUrl = (process.env.ERLAB_FRONTEND_URL || "http://127.0.0.1:5173").replace(/\/$/, "");
fs.mkdirSync(evidenceDir, { recursive: true });

const resultPath = path.join(evidenceDir, "live_run_result.json");
if (!fs.existsSync(resultPath)) {
  fs.writeFileSync(path.join(evidenceDir, "browser_verification.json"), JSON.stringify({
    status: "not_executed",
    reason: "live_run_result.json is absent",
  }, null, 2));
  process.exit(2);
}
const live = JSON.parse(fs.readFileSync(resultPath, "utf8"));
if (!live.idea_id) {
  fs.writeFileSync(path.join(evidenceDir, "browser_verification.json"), JSON.stringify({
    status: "not_executed",
    reason: "No generated paper idea_id exists",
    live_status: live.status,
  }, null, 2));
  process.exit(2);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const consoleErrors = [];
const pageErrors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text());
});
page.on("pageerror", (err) => pageErrors.push(String(err)));

const routes = [
  { name: "idea_detail", url: `${frontendUrl}/ideas/${live.idea_id}` },
  { name: "ideas_browser", url: `${frontendUrl}/ideas` },
];
const observations = [];
for (const route of routes) {
  const response = await page.goto(route.url, { waitUntil: "networkidle", timeout: 120000 });
  await page.screenshot({
    path: path.join(evidenceDir, `browser_${route.name}.png`),
    fullPage: true,
  });
  const bodyText = await page.locator("body").innerText();
  fs.writeFileSync(path.join(evidenceDir, `browser_${route.name}.txt`), bodyText);
  observations.push({
    name: route.name,
    url: page.url(),
    http_status: response ? response.status() : null,
    title: await page.title(),
    body_chars: bodyText.length,
    paper_language_visible: /paper|abstract|introduction|proposal|research/i.test(bodyText),
    error_language_visible: /internal server error|unexpected error|failed to load/i.test(bodyText),
  });
}

await browser.close();
const passed = observations.every((item) => item.http_status === 200 && item.body_chars > 50 && !item.error_language_visible)
  && pageErrors.length === 0;
const report = {
  status: passed ? "pass" : "fail",
  idea_id: live.idea_id,
  observations,
  console_errors: consoleErrors,
  page_errors: pageErrors,
};
fs.writeFileSync(path.join(evidenceDir, "browser_verification.json"), JSON.stringify(report, null, 2));
process.exit(passed ? 0 : 3);
