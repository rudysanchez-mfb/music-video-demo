// record.template.mjs - one headless 1080p Playwright video per segment, dark
// scheme, beat marks in marks.json.
//
// Copy this next to your state jar as record.mjs and REWRITE the SEGMENTS block
// for the demo at hand. Selectors must come from the app's own test hooks
// (data-testid / data-playwright / stable classnames), never guessed.
//
// Env:
//   ORIGIN                app origin (default http://localhost:3000)
//   OUTDIR                takes dir (default $MUSIC_DEMO_DIR/takes, else ./takes)
//   ONLY=a,b              record a subset
//   STATE                 storageState jar (default MUSIC_DEMO_STATE, else ~/.config/music-video-demo/state.json)
//   MUSIC_DEMO_PLAYWRIGHT path to playwright's index.mjs (default bare "playwright")
//   MUSIC_DEMO_DIR        working dir for takes (default .)
import { mkdirSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { homedir } from 'node:os';

const PW = process.env.MUSIC_DEMO_PLAYWRIGHT;
const { chromium } = PW ? await import(PW) : await import('playwright');

const ORIGIN = process.env.ORIGIN || 'http://localhost:3000';
const OUT = process.env.OUTDIR || join(process.env.MUSIC_DEMO_DIR || '.', 'takes');
const STATE = process.env.STATE
  || process.env.MUSIC_DEMO_STATE
  || join(homedir(), '.config', 'music-video-demo', 'state.json');
const ONLY = (process.env.ONLY || '').split(',').filter(Boolean);
const log = (m) => console.log(`[rec] ${m}`);
const soft = (pr) => pr.catch(() => null);
const TYPE = { delay: 55 };

// App-specific init: dismiss tours, close panels, seed local state.
// Replace or delete for the app at hand.
const INIT = () => { try {
  // localStorage.setItem('your-app.tour.dismissed', 'true');
} catch {} };

// ---- SCENES: key = route path segment. Rewrite per demo. Every scene must END
// on a full, readable screen, never on an empty state. ----
const SEGMENTS = {
  // Example: a search surface. Replace selectors with the real app's hooks.
  async search(p, mark) {
    await p.waitForSelector('input[type="search"]', { timeout: 60000 });
    await p.waitForTimeout(3500); mark('idle');
    await p.click('input[type="search"]');
    await p.type('input[type="search"]', 'example query', TYPE); mark('typed');
    await soft(p.waitForFunction(() =>
      document.querySelectorAll('article').length >= 3, null, { timeout: 45000 }));
    await p.waitForTimeout(5000); mark('results');
    mark('end');
  },

  // Example: a chat/agent surface.
  async agent(p, mark) {
    const F = 'textarea';
    await p.waitForSelector(F, { timeout: 60000 });
    await p.waitForTimeout(4000); mark('idle');
    await p.click(F); await p.type(F, 'Example request', { delay: 45 }); mark('typed');
    await p.waitForTimeout(600); await p.click('button[type="submit"]'); mark('sent');
    await soft(p.waitForSelector('.answer', { timeout: 75000 })); mark('answered');
    await p.waitForTimeout(7000); mark('end');
  },
};

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const all = {};

for (const [name, fn] of Object.entries(SEGMENTS)) {
  if (ONLY.length && !ONLY.includes(name)) continue;
  const dir = `${OUT}/${name}`;
  mkdirSync(dir, { recursive: true });
  const ctx = await browser.newContext({
    storageState: STATE,
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
    recordVideo: { dir, size: { width: 1920, height: 1080 } },
  });
  await ctx.addInitScript(INIT);
  const p = await ctx.newPage();
  const t0 = Date.now();
  const marks = [];
  const mark = (label) => {
    const t = (Date.now() - t0) / 1000;
    marks.push({ label, t });
    log(`  ${name} ${t.toFixed(1)}s ${label}`);
  };
  try {
    await p.goto(`${ORIGIN}/${name}`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    mark('loaded');
    const toDark = p.getByRole('button', { name: /switch to dark mode/i });
    if (await toDark.count()) { await toDark.first().click().catch(() => {}); await p.waitForTimeout(800); }
    await fn(p, mark);
    all[name] = { ok: true, marks };
  } catch (e) {
    log(`${name}: FAILED ${String(e).slice(0, 200)}`);
    all[name] = { ok: false, err: String(e).slice(0, 300), marks };
  }
  const video = p.video();
  await p.close();
  await ctx.close();
  renameSync(await video.path(), `${dir}/take.webm`);
  all[name].video = `${dir}/take.webm`;
  log(`${name}: ${all[name].ok ? 'ok' : 'FAILED'} -> ${dir}/take.webm`);
}

await browser.close();
writeFileSync(`${OUT}/marks.json`, JSON.stringify(all, null, 1));
log(`wrote ${OUT}/marks.json`);
