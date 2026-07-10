import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const playwrightModule =
  process.env.PLAYWRIGHT_MODULE ||
  "C:/Users/MichaelKing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright";
const { chromium } = require(playwrightModule);

const baseUrl = process.env.CANDIDATE_URL || "http://inductone-candidate.localhost:8000";
const password = process.env.CANDIDATE_TEST_PASSWORD || "InductOne-Sandbox-Test-2026!";
const evidenceRoot =
  process.env.GUI_SMOKE_EVIDENCE_DIR ||
  path.join("C:", "hub", "frappe-sandbox", "validation-evidence", `gui-smoke-${new Date().toISOString().replace(/[:.]/g, "-")}`);

fs.mkdirSync(evidenceRoot, { recursive: true });

const personas = [
  {
    label: "external-builder-motion",
    user: "motion.builder@plusonerobotics.com",
    checks: [
      access("Builder Portal workspace", "/app/builder-portal", true, false),
      access("Operations workspace denied/hidden", "/app/operations", false, false),
      access("Engineering workspace denied/hidden", "/app/engineering", false, false),
      access("BOM Export Package denied/hidden", "/app/bom-export-package", false, false),
      access("Configured BOM Snapshot denied/hidden", "/app/configured-bom-snapshot", false, false),
      access("Configuration Order assigned handoff", "/app/inductone-configuration-order", true, false),
      access("Build Completion", "/app/inductone-build-completion", true, false),
      access("Raw Item denied/no-create", "/app/item", false, false),
      access("Raw BOM denied/no-create", "/app/bom", false, false),
      access("Raw Sales Order denied/no-create", "/app/sales-order", false, false),
      access("InductOne Build denied/no-create", "/app/inductone-build", false, false),
      access("Builder Tranche denied/no-create", "/app/inductone-builder-tranche", false, false),
      access("Engineering Signoff denied/no-create", "/app/engineering-signoff", false, false),
      access("Part Number Request denied/no-create", "/app/part-number-allocation-request", false, false),
    ],
  },
  {
    label: "external-builder-lam",
    user: "lam@plusonerobotics.com",
    checks: [
      access("Builder Portal workspace", "/app/builder-portal", true, false),
      access("Operations workspace denied/hidden", "/app/operations", false, false),
      access("Engineering workspace denied/hidden", "/app/engineering", false, false),
      access("BOM Export Package denied/hidden", "/app/bom-export-package", false, false),
      access("Configured BOM Snapshot denied/hidden", "/app/configured-bom-snapshot", false, false),
      access("Configuration Order assigned handoff", "/app/inductone-configuration-order", true, false),
      access("Build Completion", "/app/inductone-build-completion", true, false),
      access("Raw Item denied/no-create", "/app/item", false, false),
      access("Raw BOM denied/no-create", "/app/bom", false, false),
      access("Raw Sales Order denied/no-create", "/app/sales-order", false, false),
    ],
  },
  {
    label: "inductone-manager-ops-christina",
    user: "christina.gt@plusonerobotics.com",
    checks: [
      access("InductOne Build create", "/app/inductone-build", true, true),
      access("BOM Export Package create", "/app/bom-export-package", true, true),
      access("Configured BOM Snapshot create", "/app/configured-bom-snapshot", true, true),
      access("Build Completion create", "/app/inductone-build-completion", true, true),
      access("Engineering Signoff create", "/app/engineering-signoff", true, true),
      access("Part Number Request create", "/app/part-number-allocation-request", true, true),
      access("Configuration Option no-create", "/app/inductone-configuration-option", true, false),
      access("Sales Order create", "/app/sales-order", true, true),
      access("Stock Entry create", "/app/stock-entry", true, true),
      access("GL Entry read/no-create", "/app/gl-entry", true, false),
    ],
  },
  {
    label: "ops-manager-jim",
    user: "jim.haws@plusonerobotics.com",
    checks: [
      access("InductOne Build create", "/app/inductone-build", true, true),
      access("Configuration Option no-create", "/app/inductone-configuration-option", true, false),
      access("Sales Order create", "/app/sales-order", true, true),
      access("Item create", "/app/item", true, true),
      access("BOM create", "/app/bom", true, true),
      access("Stock Entry create", "/app/stock-entry", true, true),
      access("Work Order create", "/app/work-order", true, true),
      access("Purchase Order create", "/app/purchase-order", true, true),
      access("GL Entry read/no-create", "/app/gl-entry", true, false),
    ],
  },
  {
    label: "engineering-user-shaun",
    user: "shaun.edwards@plusonerobotics.com",
    checks: [
      access("Engineering Signoff create", "/app/engineering-signoff", true, true),
      access("Part Number Request create", "/app/part-number-allocation-request", true, true),
      access("InductOne Build read/no-create", "/app/inductone-build", true, false),
      access("Item denied/no-create", "/app/item", false, false),
      access("Sales Order denied/no-create", "/app/sales-order", false, false),
    ],
  },
  {
    label: "operations-viewer",
    user: "candidate.operations.viewer@example.invalid",
    checks: [
      access("Item read/no-create", "/app/item", true, false),
      access("BOM read/no-create", "/app/bom", true, false),
      access("Sales Order read/no-create", "/app/sales-order", true, false),
      access("Stock Entry read/no-create", "/app/stock-entry", true, false),
      access("InductOne Build read/no-create", "/app/inductone-build", true, false),
      access("Engineering Signoff read/no-create", "/app/engineering-signoff", true, false),
    ],
  },
  {
    label: "inventory-operator",
    user: "candidate.inventory.operator@example.invalid",
    checks: [
      access("Stock Entry create", "/app/stock-entry", true, true),
      access("Delivery Note create", "/app/delivery-note", true, true),
      access("Purchase Receipt create", "/app/purchase-receipt", true, true),
      access("Item read/no-create", "/app/item", true, false),
      access("Sales Order read/no-create", "/app/sales-order", true, false),
      access("Work Order read/no-create", "/app/work-order", true, false),
    ],
  },
  {
    label: "gripper-manufacturer",
    user: "candidate.gripper.manufacturer@example.invalid",
    checks: [
      access("Work Order create", "/app/work-order", true, true),
      access("Stock Entry create", "/app/stock-entry", true, true),
      access("Item read/no-create", "/app/item", true, false),
      access("BOM read/no-create", "/app/bom", true, false),
      access("Sales Order denied/no-create", "/app/sales-order", false, false),
      access("Purchase Order denied/no-create", "/app/purchase-order", false, false),
    ],
  },
  {
    label: "finance-viewer",
    user: "candidate.finance.viewer@example.invalid",
    checks: [
      access("Sales Order read/no-create", "/app/sales-order", true, false),
      access("Purchase Invoice read/no-create", "/app/purchase-invoice", true, false),
      access("Payment Entry read/no-create", "/app/payment-entry", true, false),
      access("GL Entry read/no-create", "/app/gl-entry", true, false),
      access("Stock Entry read/no-create", "/app/stock-entry", true, false),
      access("InductOne Build read/no-create", "/app/inductone-build", true, false),
    ],
  },
  {
    label: "procurement-user",
    user: "candidate.procurement.user@example.invalid",
    checks: [
      access("Item read/write no-create", "/app/item", true, false),
      access("Supplier read/write no-create", "/app/supplier", true, false),
      access("Item Price create", "/app/item-price", true, true),
      access("Purchase Order read/no-create", "/app/purchase-order", true, false),
      access("Sales Order denied/no-create", "/app/sales-order", false, false),
      access("InductOne Build denied/no-create", "/app/inductone-build", false, false),
    ],
  },
];

const personaFilter = (process.env.GUI_SMOKE_PERSONAS || "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const selectedPersonas = personaFilter.length
  ? personas.filter((persona) => personaFilter.includes(persona.label))
  : personas;

function access(name, route, expectReadable, expectCreate) {
  return { name, route, expectReadable, expectCreate };
}

function safeName(s) {
  return s.replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "").toLowerCase();
}

async function login(page, user) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.locator('input[name="usr"], input#login_email').first().fill(user);
  await page.locator('input[name="pwd"], input#login_password').first().fill(password);
  await page.locator('button[type="submit"], button:has-text("Login")').first().click();
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(1000);
}

async function logout(page) {
  await page.goto(`${baseUrl}/api/method/logout`, { waitUntil: "domcontentloaded" }).catch(() => {});
  await page.waitForTimeout(500);
}

async function pageSignals(page) {
  const text = await page.locator("body").innerText({ timeout: 5000 }).catch(() => "");
  const title = await page.title().catch(() => "");
  const url = page.url();
  const createButtons = await page
    .locator('.page-actions .primary-action, .standard-actions .primary-action, button[data-label^="Add"], button[data-label^="%2B%20Add"]')
    .evaluateAll((nodes) =>
      nodes
        .filter((node) => {
          const style = window.getComputedStyle(node);
          const box = node.getBoundingClientRect();
          return style.visibility !== "hidden" && style.display !== "none" && box.width > 0 && box.height > 0;
        })
        .map((node) => ({
          text: (node.innerText || node.textContent || "").trim(),
          dataLabel: node.getAttribute("data-label") || "",
        }))
        .filter((node) => /(^|\+)\s*Add\b|^Add\b|^New\b/i.test(`${node.text} ${decodeURIComponent(node.dataLabel)}`))
    )
    .catch(() => []);
  const createButtonCount = createButtons.length;
  const denied = /not permitted|no permission|permission|forbidden|403|not allowed|insufficient/i.test(text);
  const login = /login|email address|password/i.test(text) && /\/login/.test(url);
  return { text, title, url, createButtonCount, createButtons, denied, login };
}

function evaluate(check, sig) {
  const readable = !sig.login && !sig.denied && !/not found|404/i.test(sig.text);
  const createVisible = sig.createButtonCount > 0;
  const readPass = check.expectReadable ? readable : !readable || !createVisible;
  const createPass = sig.denied ? !check.expectCreate : check.expectCreate ? createVisible : !createVisible;
  return {
    readable,
    createVisible,
    pass: Boolean(readPass && createPass),
    readPass,
    createPass,
  };
}

const launchOptions = { headless: true };
if (process.env.PLAYWRIGHT_EXECUTABLE_PATH) {
  launchOptions.executablePath = process.env.PLAYWRIGHT_EXECUTABLE_PATH;
}
const browser = await chromium.launch(launchOptions);
const results = [];

try {
  for (const persona of selectedPersonas) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    await login(page, persona.user);
    const loginShot = path.join(evidenceRoot, `${persona.label}__login.png`);
    await page.screenshot({ path: loginShot, fullPage: true });
    for (const check of persona.checks) {
      const checkId = `${persona.label}__${safeName(check.name)}`;
      const started = new Date().toISOString();
      let sig;
      let error = null;
      try {
        await page.goto(`${baseUrl}${check.route}`, { waitUntil: "domcontentloaded", timeout: 30000 });
        await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
        await page.waitForTimeout(1200);
        sig = await pageSignals(page);
      } catch (e) {
        error = String(e?.message || e);
        sig = { text: "", title: "", url: page.url(), addButtonCount: 0, newButtonCount: 0, denied: false, login: false };
      }
      const screenshot = path.join(evidenceRoot, `${checkId}.png`);
      await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {});
      const evalResult = evaluate(check, sig);
      results.push({
        persona: persona.label,
        user: persona.user,
        check: check.name,
        route: check.route,
        expected: { readable: check.expectReadable, create: check.expectCreate },
        observed: {
          url: sig.url,
          title: sig.title,
          denied: sig.denied,
          login: sig.login,
          createButtonCount: sig.createButtonCount,
          createButtons: sig.createButtons,
          readable: evalResult.readable,
          createVisible: evalResult.createVisible,
          bodyExcerpt: sig.text.slice(0, 500),
        },
        pass: evalResult.pass,
        error,
        screenshot,
        started,
        finished: new Date().toISOString(),
      });
    }
    await logout(page);
    await context.close();
  }
} finally {
  await browser.close();
}

const jsonPath = path.join(evidenceRoot, "gui-smoke-results.json");
fs.writeFileSync(jsonPath, JSON.stringify({ baseUrl, evidenceRoot, results }, null, 2));

const lines = [];
lines.push("# Candidate GUI Smoke Test Results");
lines.push("");
lines.push(`- Base URL: ${baseUrl}`);
lines.push(`- Evidence folder: ${evidenceRoot}`);
lines.push(`- Generated: ${new Date().toISOString()}`);
lines.push("");
lines.push("| Result | Persona | User | Check | Route | Evidence | Notes |");
lines.push("|---|---|---|---|---|---|---|");
for (const r of results) {
  const rel = path.basename(r.screenshot);
  const notes = r.error
    ? `Error: ${r.error.replace(/\|/g, "\\|")}`
    : `readable=${r.observed.readable}; createVisible=${r.observed.createVisible}; denied=${r.observed.denied}`;
  lines.push(
    `| ${r.pass ? "PASS" : "FAIL"} | ${r.persona} | ${r.user} | ${r.check} | ${r.route} | ${rel} | ${notes} |`
  );
}
const mdPath = path.join(evidenceRoot, "gui-smoke-results.md");
fs.writeFileSync(mdPath, lines.join("\n") + "\n");

const failed = results.filter((r) => !r.pass);
console.log(JSON.stringify({ evidenceRoot, total: results.length, passed: results.length - failed.length, failed: failed.length, failedChecks: failed.map((r) => ({ persona: r.persona, check: r.check, route: r.route, screenshot: r.screenshot })) }, null, 2));

if (failed.length) {
  process.exitCode = 2;
}
