// Rasterise the example SVGs to PNG with the pre-installed Chromium.
// Usage: node scripts/render_art.mjs   (from web/)
import { chromium } from 'playwright';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, '..', '..', 'server', 'scripts', 'example_art');
const out = join(here, '..', '..', 'server', 'app', 'examples', 'data');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 800, height: 800 } });
for (const f of readdirSync(src).filter((f) => f.endsWith('.svg'))) {
  const svg = readFileSync(join(src, f), 'utf8');
  await page.setContent(`<html><body style="margin:0">${svg}</body></html>`);
  await page.screenshot({ path: join(out, f.replace('.svg', '.png')), clip: { x: 0, y: 0, width: 800, height: 800 } });
  console.log('rendered', f);
}
await browser.close();
