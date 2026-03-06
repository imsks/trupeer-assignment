import { chromium } from 'playwright';
const errors = [];
const browser = await chromium.launch();
const page = await browser.newPage();
page.on('console', msg => {
  const type = msg.type();
  const text = msg.text();
  if (type === 'error' || type === 'warning') errors.push({ type, text });
});
await page.goto('http://localhost:5173/', { waitUntil: 'domcontentloaded', timeout: 15000 });
await page.waitForTimeout(2000); // Let Three.js and video load
await page.screenshot({ path: 'video-player-screenshot.png', fullPage: true });
console.log('CONSOLE_ERRORS:' + JSON.stringify(errors));
await browser.close();
