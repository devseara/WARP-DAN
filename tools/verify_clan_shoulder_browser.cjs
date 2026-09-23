// Exercise the unchanged-export shoulder comparison in both coordinate modes.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const out = path.resolve(__dirname, '../Assets/ClanBodySkins/shoulder-audit-20260924');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
  try {
    const page = await browser.newPage({viewport: {width: 1200, height: 800}});
    const errors = [], loops = [];
    page.on('pageerror', e => errors.push(String(e)));
    page.on('requestfailed', r => errors.push(r.url()));
    await page.goto('http://127.0.0.1:8808/shoulder-audit-20260924/review.html', {waitUntil: 'networkidle'});
    await page.waitForFunction(() => document.body.dataset.ready === 'true');
    for (const job of ['acolyte', 'archer']) for (const sex of ['male', 'female']) {
      await page.selectOption('#job', job);
      await page.selectOption('#sex', sex);
      for (const direction of [5, 7]) for (const mode of ['raw', 'aligned']) {
        await page.selectOption('#dir', String(direction));
        await page.selectOption('#mode', mode);
        await page.evaluate(async () => {frame = 0; await draw();});
        const frames = await page.evaluate(() => new Promise((resolve, reject) => {
          const seen = new Set();
          const obs = new MutationObserver(() => {
            seen.add(document.getElementById('slider').value);
            if (seen.size === 8) {
              clearTimeout(timeout); obs.disconnect(); playing = false; schedule(); resolve([...seen]);
            }
          });
          const timeout = setTimeout(() => {obs.disconnect(); playing = false; schedule(); reject(Error('Incomplete cycle'));}, 5000);
          obs.observe(document.getElementById('status'), {childList: true, subtree: true});
          playing = true; schedule();
        }));
        loops.push({job, sex, direction, mode, frames});
      }
    }
    await page.selectOption('#job', 'archer');
    await page.selectOption('#sex', 'female');
    await page.selectOption('#dir', '5');
    for (const f of [4, 5, 6]) {
      await page.evaluate(async f => {frame = f; await draw();}, f);
      await page.screenshot({path: path.join(out, `browser-archer-female-d5-f${f}.png`)});
    }
    if (errors.length) throw Error(errors.join('\n'));
    fs.writeFileSync(path.join(out, 'browser-verification.json'), JSON.stringify({status: 'passed', browser: await browser.version(), loops, errors, scope: 'Playback execution and screenshots; not user acceptance or game-client validation.'}, null, 2));
    console.log(JSON.stringify({status: 'passed', cycles: loops.length, frames: loops.reduce((n, l) => n + l.frames.length, 0)}));
  } finally {await browser.close();}
})().catch(e => {console.error(e); process.exitCode = 1;});
