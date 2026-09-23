// Render the homepage example images with the site's own 3D viewer.
// Needs the API running with the website built:  node scripts/render_examples.mjs [baseUrl]
import { chromium } from 'playwright';
import { join, dirname } from 'node:path';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const base = process.argv[2] ?? 'http://127.0.0.1:8000';
const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'examples');
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await browser.newPage({ viewport: { width: 900, height: 900 }, deviceScaleFactor: 1 });
const { examples } = await (await fetch(`${base}/api/store/examples`)).json();
for (const ex of examples) {
  await page.goto(`${base}/render/${ex.model_id}?size=900`);
  await page.waitForFunction(() => window.__rendered === true, null, { timeout: 60000 });
  await page.screenshot({ path: join(out, `${ex.slug}.png`), omitBackground: true, clip: { x: 0, y: 0, width: 900, height: 900 } });
  console.log('rendered', ex.slug);
}
await browser.close();
