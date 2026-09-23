// End-to-end smoke test of the whole purchase flow in a real browser.
//   node scripts/e2e.mjs [baseUrl] [photo] [screenshotDir]
// Needs the API running (test payments, BRICKSNAP_ADMIN_TOKEN=opstest).
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const base = process.argv[2] ?? 'http://127.0.0.1:8000';
const photo = process.argv[3];
const shots = process.argv[4] ?? '/tmp/kitsnap-e2e';
mkdirSync(shots, { recursive: true });
const gl = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'];
const browser = await chromium.launch({ args: gl });
const step = (m) => console.log(`[${new Date().toISOString().slice(11, 19)}] ${m}`);

async function run(name, viewport, isMobile) {
  const ctx = await browser.newContext({ viewport, isMobile, hasTouch: isMobile, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  const shot = (s) => page.screenshot({ path: `${shots}/${name}-${s}.png`, fullPage: s === 'home' });

  await page.goto(base + '/');
  await page.waitForSelector('.example b', { timeout: 20000 });
  await page.waitForTimeout(2500);
  await shot('home');
  step(`${name}: home ok`);

  // force: software GL in CI makes the turning hero slow enough to starve
  // Playwright's stability check; a real phone GPU does not.
  await page.getByRole('link', { name: /Create My Set/ }).first().click({ force: true });
  await page.waitForSelector('.drop');
  await page.locator('input[type=file][multiple]').setInputFiles(photo);
  await page.waitForSelector('.thumb img');
  await shot('upload');
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('radio', { name: 'Pet' }).click();
  await shot('subject');
  await page.getByRole('button', { name: /Continue/ }).click();
  await page.getByRole('radio', { name: /MINI/ }).click();
  await shot('size');
  await page.getByRole('button', { name: /Build my set/ }).click();
  await page.waitForURL(/\/build\//);
  await page.waitForSelector('.stage.is-active', { timeout: 20000 });
  await shot('building');
  step(`${name}: building`);
  await page.waitForURL(/\/design\//, { timeout: 180000 });
  await page.waitForSelector('.stat-box b');
  await page.waitForTimeout(2500);
  await shot('design');
  step(`${name}: design ${page.url()}`);

  await page.getByRole('tab', { name: /Instructions/ }).click();
  await page.waitForSelector('.steps__add', { timeout: 20000 });
  await page.getByRole('button', { name: 'Next step' }).click();
  await page.waitForTimeout(800);
  await shot('instructions');
  await page.getByRole('tab', { name: /Parts/ }).click();

  await page.getByRole('button', { name: /Approve this design/ }).click();
  await page.getByRole('link', { name: /Order this set/ }).click();
  await page.waitForSelector('#email');
  await page.fill('#email', 'test@example.com');
  await page.fill('#name', 'Test Customer');
  await page.fill('#phone', '050-0000000');
  await page.fill('#line1', '1 Herzl St');
  await page.fill('#city', 'Tel Aviv');
  await page.fill('#postal', '6100000');
  await page.getByText('Express').click();
  await shot('checkout');
  await page.getByRole('button', { name: /Continue to/ }).click();
  await page.waitForURL(/checkout\/test\//);
  await shot('testpay');
  await page.getByRole('button', { name: /Complete test payment/ }).click();
  await page.waitForURL(/\/order\//);
  await page.waitForSelector('.timeline');
  await shot('order');
  step(`${name}: ordered ${page.url()}`);
  if (errors.length) step(`${name}: browser errors:\n  ` + errors.join('\n  '));
  await ctx.close();
  return errors.length;
}

let bad = 0;
if (!process.env.PHONE_ONLY) bad += await run('desktop', { width: 1440, height: 900 }, false);
bad += await run('phone', { width: 390, height: 844 }, true);
await browser.close();
process.exit(bad ? 1 : 0);
