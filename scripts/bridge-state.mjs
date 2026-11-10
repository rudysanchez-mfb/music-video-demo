// bridge-state.mjs - dump an authed headed CDP Chrome session into a Playwright
// storageState jar, so record.mjs can reuse it.
//
// Legacy lane: prefer creating the jar with a headed login you perform yourself
// (see README, "Auth and probe"). This file harvests from a Chrome you already
// have open with remote debugging enabled.
//
// Env:
//   ORIGIN        app origin (default http://localhost:3000)
//   PROBE_PATH    path to load (default /)
//   OUT           output jar (default MUSIC_DEMO_STATE, else ~/.config/music-video-demo/state.json)
//   CDP           CDP endpoint (default http://127.0.0.1:9222)
//   MUSIC_DEMO_PLAYWRIGHT  path to playwright's index.mjs (default bare "playwright")
import { writeFileSync, existsSync, readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { homedir } from 'node:os';

const PW = process.env.MUSIC_DEMO_PLAYWRIGHT;
const { chromium } = PW ? await import(PW) : await import('playwright');

const JAR_PATH = process.env.MUSIC_DEMO_STATE
  || join(homedir(), '.config', 'music-video-demo', 'state.json');

async function mergeIntoJar(state) {
  let jar = { cookies: [], origins: [] };
  if (existsSync(JAR_PATH)) {
    try { jar = JSON.parse(readFileSync(JAR_PATH, 'utf8')); } catch {}
  }
  const key = (c) => `${c.domain}|${c.path}|${c.name}`;
  const cookies = new Map((jar.cookies || []).map((c) => [key(c), c]));
  for (const c of state.cookies) cookies.set(key(c), c);
  const origins = new Map((jar.origins || []).map((o) => [o.origin, o]));
  for (const o of state.origins) origins.set(o.origin, o);
  writeFileSync(JAR_PATH,
    JSON.stringify({ cookies: [...cookies.values()], origins: [...origins.values()] }, null, 1),
    { mode: 0o600 });
  return { cookies: cookies.size, origins: origins.size };
}

const ORIGIN = process.env.ORIGIN || 'http://localhost:3000';
const PROBE = process.env.PROBE_PATH || '/';
const OUT = process.env.OUT || JAR_PATH;
const browser = await chromium.connectOverCDP(process.env.CDP || 'http://127.0.0.1:9222');
const ctx = browser.contexts()[0];
const page = await ctx.newPage();
await page.goto(ORIGIN + PROBE, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(6000);
console.log('url after load:', page.url(), '| title:', await page.title());

const cdp = await ctx.newCDPSession(page);
const { cookies } = await cdp.send('Network.getAllCookies');
const host = new URL(ORIGIN).hostname;
const apex = host.split('.').slice(-2).join('.');
const keep = cookies.filter((c) => c.domain.replace(/^\./, '').endsWith(apex));
const ls = await page.evaluate(() =>
  Object.entries(localStorage).map(([name, value]) => ({ name, value })));

const state = {
  cookies: keep.map((c) => ({
    name: c.name, value: c.value, domain: c.domain, path: c.path,
    expires: c.expires ?? -1, httpOnly: !!c.httpOnly, secure: !!c.secure,
    sameSite: c.sameSite === 'Strict' ? 'Strict' : c.sameSite === 'Lax' ? 'Lax' : 'None',
  })),
  origins: [{ origin: ORIGIN, localStorage: ls }],
};

if (resolve(OUT) === JAR_PATH) {
  console.log('merged into canonical jar:', JSON.stringify(await mergeIntoJar(state)));
} else {
  writeFileSync(OUT, JSON.stringify(state, null, 1));
}
console.log(`cookies kept: ${keep.length}, localStorage keys: ${ls.length} -> ${OUT}`);
console.log('body text head:',
  (await page.evaluate(() => document.body.innerText.slice(0, 300))).replace(/\n+/g, ' | '));
await page.close();
await browser.close();
