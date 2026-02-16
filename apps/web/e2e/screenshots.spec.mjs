/**
 * Visual Screenshot Tests
 *
 * Captures screenshots of every major page for documentation and visual regression.
 * Run:  npm run test:screenshots
 * Output: docs/screenshots/
 *
 * Requirements:
 *   - Frontend running on http://localhost:4321
 *   - Backend running on http://localhost:8002
 *   - npx playwright install chromium (first time only)
 */

import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.env.BASE_URL || "http://localhost:4321";
const OUT_DIR = resolve(__dirname, "../../../docs/screenshots");
const ARENA_TOPIC = "Compare PostgreSQL vs MySQL vs SQLite for web applications";

// Ensure output directory exists
mkdirSync(OUT_DIR, { recursive: true });

/** Helper: navigate and screenshot with consistent settings */
async function capture(ctx, name, path, opts = {}) {
  const { waitFor = "domcontentloaded", delay = 1500, fn } = opts;
  const page = opts.page || (await ctx.newPage());

  if (!opts.page) {
    await page.goto(`${BASE_URL}${path}`, { waitUntil: waitFor, timeout: 15000 });
  }

  if (fn) await fn(page);
  if (delay) await page.waitForTimeout(delay);

  await page.screenshot({ path: resolve(OUT_DIR, `${name}.png`) });
  console.log(`  ✓ ${name}.png`);

  if (!opts.keepOpen) await page.close();
  return page;
}

async function main() {
  console.log(`\nCapturing screenshots → ${OUT_DIR}\n`);
  console.log(`Base URL: ${BASE_URL}\n`);

  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  let passed = 0;
  let failed = 0;

  // ── Static pages ──

  const staticPages = [
    ["dashboard", "/"],
    ["search", "/search"],
    ["ai-coach", "/ai"],
    ["research", "/research"],
    ["arena-empty", "/arena"],
  ];

  for (const [name, path] of staticPages) {
    try {
      await capture(ctx, name, path);
      passed++;
    } catch (err) {
      console.error(`  ✗ ${name}: ${err.message}`);
      failed++;
    }
  }

  // ── Arena flow (multi-step) ──

  try {
    console.log("\n  Arena flow:");

    // Open arena page
    const arenaPage = await ctx.newPage();
    await arenaPage.goto(`${BASE_URL}/arena`, { waitUntil: "domcontentloaded", timeout: 15000 });
    await arenaPage.waitForTimeout(1000);

    // Type topic
    const input = arenaPage.locator('input[type="text"]');
    await input.fill(ARENA_TOPIC);
    await arenaPage.waitForTimeout(500);
    await arenaPage.screenshot({ path: resolve(OUT_DIR, "arena-input.png") });
    console.log("    ✓ arena-input.png");
    passed++;

    // Launch arena
    const launchBtn = arenaPage.locator('button:has-text("Launch Arena")');
    await launchBtn.click();

    // Wait for Alpha to start streaming
    await arenaPage.waitForTimeout(6000);
    await arenaPage.screenshot({ path: resolve(OUT_DIR, "arena-alpha-streaming.png") });
    console.log("    ✓ arena-alpha-streaming.png");
    passed++;

    // Wait for Beta
    await arenaPage.waitForTimeout(20000);
    await arenaPage.screenshot({ path: resolve(OUT_DIR, "arena-beta-streaming.png") });
    console.log("    ✓ arena-beta-streaming.png");
    passed++;

    // Wait for completion (Gamma)
    await arenaPage.waitForTimeout(35000);
    await arenaPage.screenshot({ path: resolve(OUT_DIR, "arena-complete.png") });
    console.log("    ✓ arena-complete.png");
    passed++;

    await arenaPage.close();
  } catch (err) {
    console.error(`  ✗ Arena flow: ${err.message}`);
    failed++;
  }

  await browser.close();

  // ── Summary ──

  console.log(`\n─────────────────────────────`);
  console.log(`Screenshots: ${passed} captured, ${failed} failed`);
  console.log(`Output: ${OUT_DIR}`);
  console.log(`─────────────────────────────\n`);

  process.exit(failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
