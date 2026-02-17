#!/usr/bin/env node
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const APP_URL = process.env.APP_URL || 'http://localhost:3000';
const SCREENSHOTS_DIR = path.join(process.cwd(), 'screenshots');
const SCREENSHOT_PREFIX = process.env.SCREENSHOT_PREFIX || 'visual-check';
const PAGES = (process.env.SCREENSHOT_PAGES || process.env.SCREENSHOT_DEFAULT_PAGES || '/').split(',').map(p => p.trim());
const VIEWPORT_WIDTH = parseInt(process.env.SCREENSHOT_VIEWPORT_WIDTH || '1280', 10);
const VIEWPORT_HEIGHT = parseInt(process.env.SCREENSHOT_VIEWPORT_HEIGHT || '720', 10);
const TIMEOUT = parseInt(process.env.SCREENSHOT_TIMEOUT || '30000', 10);
const WAIT = parseInt(process.env.SCREENSHOT_WAIT || '1000', 10);
const TEXT_PREVIEW = parseInt(process.env.SCREENSHOT_TEXT_PREVIEW || '300', 10);
const TEXT_SHORT = parseInt(process.env.SCREENSHOT_TEXT_SHORT || '150', 10);

async function run() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  try {
    const context = await browser.newContext({ viewport: { width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT } });
    const summaries = [];

    for (let i = 0; i < PAGES.length; i++) {
      const pagePath = PAGES[i];
      const url = pagePath.startsWith('http') ? pagePath : `${APP_URL}${pagePath}`;
      const page = await context.newPage();

      console.log(`📸 Screenshotting: ${url}`);
      await page.goto(url, { waitUntil: 'networkidle', timeout: TIMEOUT });
      await page.waitForTimeout(WAIT);

      const screenshotFile = path.join(SCREENSHOTS_DIR, `${SCREENSHOT_PREFIX}-${String(i + 1).padStart(2, '0')}.png`);
      await page.screenshot({ path: screenshotFile, fullPage: true });

      const title = await page.title();
      const visibleText = await page.evaluate(() => {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
          acceptNode: (node) => {
            const p = node.parentElement;
            if (!p) return NodeFilter.FILTER_REJECT;
            const s = window.getComputedStyle(p);
            if (s.display === 'none' || s.visibility === 'hidden') return NodeFilter.FILTER_REJECT;
            return node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
          }
        });
        const t = []; let n;
        while (n = walker.nextNode()) t.push(n.textContent.trim());
        return t.join(' ');
      });

      summaries.push({ url, title, screenshot: path.basename(screenshotFile), visibleText: visibleText.substring(0, TEXT_PREVIEW) });
      await page.close();
    }

    console.log('\n' + '='.repeat(60));
    console.log('📊 SCREENSHOT SUMMARY');
    console.log('='.repeat(60));
    summaries.forEach(s => {
      console.log(`\nPage: ${s.url}`);
      console.log(`Title: ${s.title}`);
      console.log(`Screenshot: ${s.screenshot}`);
      console.log(`Content: "${s.visibleText.substring(0, TEXT_SHORT)}..."`);
    });
    console.log('\n' + '='.repeat(60));

    fs.writeFileSync(path.join(SCREENSHOTS_DIR, `${SCREENSHOT_PREFIX}-report.json`), JSON.stringify({ success: true, pages: summaries }, null, 2));
  } finally {
    await browser.close();
  }
}

run().then(() => { console.log('✅ Done'); process.exit(0); }).catch(e => { console.error('❌', e); process.exit(1); });

