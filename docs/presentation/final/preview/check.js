// Run from the repo root: node docs/presentation/final/preview/check.js docs/presentation/final/deck <out-dir> [slide ids]
// Local preview of deck slide files: renders each <section> at 1920x1080 with the deck fonts,
// reports mid-word line breaks, overflow past the safe area, text/image overlaps; saves PNGs.
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const root = process.argv[2]; const outDir = process.argv[3]; const only = process.argv.slice(4);
const deck = JSON.parse(fs.readFileSync(path.join(root, 'project/deck.json'), 'utf8'));
const blobDir = process.env.BLOBS || '';
const blobMap = JSON.parse(fs.readFileSync(path.join(__dirname, 'blobs.json'), 'utf8'));
const css = `
*{margin:0;box-sizing:border-box}
body{margin:0;background:#888}
section{width:1920px;height:1080px;position:relative;overflow:hidden;display:flex;flex-direction:column}
div:not([style*="display"]){display:flex;flex-direction:column}
h1{font-size:96px;font-weight:600;line-height:1.1}
h2{font-size:64px;font-weight:600;line-height:1.15}
h3{font-size:44px;font-weight:600;line-height:1.2}
p{font-size:32px;font-weight:400;line-height:1.4}
ul{padding-left:1.2em} li{line-height:inherit}
aside{display:none}
section > :not([style*="position:absolute"]){position:relative;z-index:1}
x-shape{display:block;flex:none}
x-connector{display:none}
img{display:block;flex:none}
table{border-collapse:collapse} td,th{padding:0.35em 0.6em;border-bottom:1px solid #ccd}
`;
(async () => {
  const browser = await chromium.launch({ proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined, args: ['--ignore-certificate-errors'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const report = [];
  for (const id of deck.order) {
    if (only.length && !only.includes(id)) continue;
    let html = fs.readFileSync(path.join(root, 'project/slides', id + '.html'), 'utf8');
    html = html.replace(/\/_blob\/([0-9a-f]{32})/g, (m, b) => 'file://' + path.resolve(blobMap[b]));
    const doc = `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300..900&family=DM+Sans:wght@400..800&display=block">
<style>${css}</style></head><body>${html}</body></html>`;
    for (const m of html.matchAll(/padding:([^;"]+)/g)) for (const v of m[1].match(/\d+/g) || []) if (+v > 256) report.push({ id: id + ' (lint)', issues: [{ kind: 'padding>256', v }] });
    const f = path.join(outDir, id + '.html'); fs.writeFileSync(f, doc);
    await page.goto('file://' + f, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    const issues = await page.evaluate(() => {
      const out = []; const sec = document.querySelector('section');
      const isSpace = c => /\s/.test(c);
      const els = sec.querySelectorAll('h1,h2,h3,p,li,td,th');
      for (const el of els) {
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        let prev = null; let n;
        while ((n = walker.nextNode())) {
          const t = n.textContent;
          for (let i = 0; i < t.length; i++) {
            if (isSpace(t[i])) { prev = null; continue; }
            const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + 1);
            const rect = r.getClientRects()[0]; if (!rect) continue;
            if (prev && rect.top > prev.top + 4 && !prev.br) out.push({ kind: 'midword', text: (prev.ch + t[i]), ctx: el.textContent.slice(0, 40) });
            prev = { top: rect.top, ch: t[i], br: false };
          }
          // a <br> between text nodes resets
          if (n.nextSibling && n.nextSibling.nodeName === 'BR') prev = null;
        }
        // line count vs explicit <br>
        const tops = new Set(); const rng = document.createRange(); rng.selectNodeContents(el);
        for (const rr of rng.getClientRects()) if (rr.width > 1) tops.add(Math.round(rr.top / 4));
        const brs = el.querySelectorAll('br').length;
        if (el.tagName !== 'TD' && el.tagName !== 'TH' && el.tagName !== 'LI' && tops.size > brs + 1) out.push({ kind: 'autowrap', lines: tops.size, brs, ctx: el.textContent.slice(0, 40) });
        const tb = rng.getBoundingClientRect(); const eb = el.getBoundingClientRect();
        if (tb.right > eb.right + 2 || tb.left < eb.left - 2) out.push({ kind: 'text-overflow', over: Math.round(tb.right - eb.right), ctx: el.textContent.slice(0, 40) });
        let par = el.parentElement;
        while (par && par.tagName !== 'SECTION') { const cs = getComputedStyle(par); if (cs.backgroundColor !== 'rgba(0, 0, 0, 0)' || cs.borderTopWidth !== '0px') break; par = par.parentElement; }
        if (par && par.tagName !== 'SECTION') { const pb = par.getBoundingClientRect(); const pr = parseFloat(getComputedStyle(par).paddingRight) || 0; if (tb.right > pb.right - pr + 6) out.push({ kind: 'past-card', over: Math.round(tb.right - (pb.right - pr)), ctx: el.textContent.slice(0, 40) }); }
        const r = el.getBoundingClientRect();
        const pinned = getComputedStyle(el).position === 'absolute';
        if (!pinned && r.bottom > 925) out.push({ kind: 'below-safe', bottom: Math.round(r.bottom), ctx: el.textContent.slice(0, 40) });
        if (r.right > 1795 || r.left < 125) out.push({ kind: 'outside-x', left: Math.round(r.left), right: Math.round(r.right), ctx: el.textContent.slice(0, 40) });
        if (el.scrollWidth > el.clientWidth + 2) out.push({ kind: 'overflow-x', ctx: el.textContent.slice(0, 40) });
      }
      // text vs image overlaps
      const imgs = [...sec.querySelectorAll('img')].map(i => i.getBoundingClientRect());
      for (const el of els) {
        const r = el.getBoundingClientRect();
        for (const ir of imgs) {
          const ox = Math.min(r.right, ir.right) - Math.max(r.left, ir.left);
          const oy = Math.min(r.bottom, ir.bottom) - Math.max(r.top, ir.top);
          if (ox > 4 && oy > 4) out.push({ kind: 'over-image', ctx: el.textContent.slice(0, 40) });
        }
      }
      return out;
    });
    await page.screenshot({ path: path.join(outDir, id + '.png') });
    report.push({ id, issues });
  }
  await browser.close();
  for (const r of report) { console.log('## ' + r.id + (r.issues.length ? '' : '  OK')); for (const i of r.issues) console.log('  ', JSON.stringify(i)); }
})();
