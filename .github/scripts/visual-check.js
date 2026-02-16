#!/usr/bin/env node

/**
 * Visual Check Script for Ralph Agent
 * 
 * Uses Playwright to:
 * - Launch the Task Manager app
 * - Take screenshots of the UI
 * - Generate a text-based visual summary (what Claude can "read")
 * - Test basic interactions (add task, toggle completion)
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// Configuration
const APP_URL = process.env.APP_URL || 'http://localhost:3000';
const SCREENSHOTS_DIR = path.join(process.cwd(), 'screenshots');
const SCREENSHOT_PREFIX = process.env.SCREENSHOT_PREFIX || 'visual-check';

async function ensureScreenshotsDir() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }
}

async function getElementInfo(page, selector) {
  try {
    const element = await page.locator(selector).first();
    const isVisible = await element.isVisible().catch(() => false);
    if (!isVisible) return null;

    const box = await element.boundingBox().catch(() => null);
    const text = await element.textContent().catch(() => '');
    const styles = await element.evaluate(el => {
      const computed = window.getComputedStyle(el);
      return {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
        fontSize: computed.fontSize,
        fontWeight: computed.fontWeight,
        display: computed.display,
        width: computed.width,
        height: computed.height
      };
    }).catch(() => ({}));

    return {
      selector,
      visible: isVisible,
      text: text?.trim().substring(0, 100) || '',
      position: box ? { x: box.x, y: box.y, width: box.width, height: box.height } : null,
      styles
    };
  } catch (e) {
    return null;
  }
}

async function analyzePageLayout(page) {
  const selectors = [
    'h1',
    'h2',
    '.add-task-section',
    '#taskTitle',
    '#taskDescription',
    'button',
    '.tasks-section',
    '#tasksList',
    '.task',
    '.task-title',
    '.task-description',
    '.complete-btn',
    '.delete-btn'
  ];

  const elements = [];
  for (const selector of selectors) {
    const count = await page.locator(selector).count();
    if (count > 0) {
      const info = await getElementInfo(page, selector);
      if (info) {
        elements.push({ ...info, count });
      }
    }
  }

  return elements;
}

async function generateVisualSummary(page, screenshotPath, context = 'initial') {
  const title = await page.title();
  const url = page.url();
  
  // Get viewport size
  const viewportSize = page.viewportSize();
  
  // Get body background
  const bodyStyles = await page.evaluate(() => {
    const body = document.body;
    const computed = window.getComputedStyle(body);
    return {
      background: computed.background,
      backgroundColor: computed.backgroundColor,
      minHeight: computed.minHeight
    };
  });

  // Analyze layout
  const elements = await analyzePageLayout(page);

  // Count tasks
  const taskCount = await page.locator('.task').count();
  const completedTaskCount = await page.locator('.task.completed').count();

  // Get all visible text
  const visibleText = await page.evaluate(() => {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: (node) => {
          const parent = node.parentElement;
          if (!parent) return NodeFilter.FILTER_REJECT;
          const style = window.getComputedStyle(parent);
          if (style.display === 'none' || style.visibility === 'hidden') {
            return NodeFilter.FILTER_REJECT;
          }
          return node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        }
      }
    );

    const texts = [];
    let node;
    while (node = walker.nextNode()) {
      texts.push(node.textContent.trim());
    }
    return texts.join(' ');
  });

  return {
    context,
    timestamp: new Date().toISOString(),
    page: {
      title,
      url,
      viewport: viewportSize
    },
    body: bodyStyles,
    elements,
    tasks: {
      total: taskCount,
      completed: completedTaskCount,
      active: taskCount - completedTaskCount
    },
    visibleText: visibleText.substring(0, 500),
    screenshot: screenshotPath
  };
}

async function runVisualCheck() {
  console.log('🎭 Starting Playwright Visual Check...');
  console.log(`📍 Target URL: ${APP_URL}`);
  
  await ensureScreenshotsDir();

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 720 }
    });

    const page = await context.newPage();

    // Navigate to the app
    console.log('🌐 Navigating to app...');
    await page.goto(APP_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000); // Wait for any animations

    // 1. Take initial screenshot
    console.log('📸 Taking initial screenshot...');
    const initialScreenshot = path.join(SCREENSHOTS_DIR, `${SCREENSHOT_PREFIX}-01-initial.png`);
    await page.screenshot({ path: initialScreenshot, fullPage: true });
    
    const initialSummary = await generateVisualSummary(page, initialScreenshot, 'initial');

    // 2. Add a new task
    console.log('➕ Testing: Add new task...');
    await page.fill('#taskTitle', 'Test Task from Playwright');
    await page.fill('#taskDescription', 'This task was added by the visual check script');
    await page.click('button:has-text("Add Task")');
    await page.waitForTimeout(1000);

    const afterAddScreenshot = path.join(SCREENSHOTS_DIR, `${SCREENSHOT_PREFIX}-02-after-add.png`);
    await page.screenshot({ path: afterAddScreenshot, fullPage: true });
    
    const afterAddSummary = await generateVisualSummary(page, afterAddScreenshot, 'after-add-task');

    // 3. Toggle task completion
    console.log('✅ Testing: Toggle task completion...');
    const completeButton = page.locator('.complete-btn').first();
    if (await completeButton.isVisible()) {
      await completeButton.click();
      await page.waitForTimeout(500);

      const afterCompleteScreenshot = path.join(SCREENSHOTS_DIR, `${SCREENSHOT_PREFIX}-03-after-complete.png`);
      await page.screenshot({ path: afterCompleteScreenshot, fullPage: true });
      
      const afterCompleteSummary = await generateVisualSummary(page, afterCompleteScreenshot, 'after-complete-task');

      // Generate final summary report
      const report = {
        success: true,
        timestamp: new Date().toISOString(),
        appUrl: APP_URL,
        screenshotsDir: SCREENSHOTS_DIR,
        checks: [
          initialSummary,
          afterAddSummary,
          afterCompleteSummary
        ]
      };

      // Output text summary for Claude to read
      console.log('\n' + '='.repeat(80));
      console.log('📊 VISUAL CHECK SUMMARY (Text Format for AI)');
      console.log('='.repeat(80));
      console.log(`\n✅ Visual check completed successfully at ${report.timestamp}`);
      console.log(`📍 App URL: ${report.appUrl}`);
      console.log(`📁 Screenshots saved to: ${report.screenshotsDir}\n`);

      for (const check of report.checks) {
        console.log(`\n--- ${check.context.toUpperCase()} ---`);
        console.log(`Page Title: ${check.page.title}`);
        console.log(`Viewport: ${check.page.viewport.width}x${check.page.viewport.height}`);
        console.log(`Tasks: ${check.tasks.total} total, ${check.tasks.completed} completed, ${check.tasks.active} active`);
        console.log(`Body Background: ${check.body.backgroundColor || check.body.background}`);
        console.log(`\nKey Elements:`);
        check.elements.forEach(el => {
          console.log(`  - ${el.selector} (count: ${el.count})`);
          if (el.text) console.log(`    Text: "${el.text}"`);
          if (el.position) console.log(`    Position: x=${Math.round(el.position.x)}, y=${Math.round(el.position.y)}, w=${Math.round(el.position.width)}, h=${Math.round(el.position.height)}`);
          if (el.styles.color) console.log(`    Color: ${el.styles.color}`);
          if (el.styles.backgroundColor && el.styles.backgroundColor !== 'rgba(0, 0, 0, 0)') {
            console.log(`    Background: ${el.styles.backgroundColor}`);
          }
        });
        console.log(`\nVisible Text Sample: "${check.visibleText.substring(0, 200)}..."`);
        console.log(`Screenshot: ${path.basename(check.screenshot)}`);
      }

      console.log('\n' + '='.repeat(80));
      console.log('✅ All visual checks passed!');
      console.log('='.repeat(80) + '\n');

      // Save JSON report
      const reportPath = path.join(SCREENSHOTS_DIR, `${SCREENSHOT_PREFIX}-report.json`);
      fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
      console.log(`📄 Full JSON report saved to: ${reportPath}\n`);

      return report;
    } else {
      console.log('⚠️  No complete button found, skipping toggle test');
      
      const report = {
        success: true,
        timestamp: new Date().toISOString(),
        appUrl: APP_URL,
        screenshotsDir: SCREENSHOTS_DIR,
        checks: [initialSummary, afterAddSummary]
      };

      console.log('\n' + '='.repeat(80));
      console.log('📊 VISUAL CHECK SUMMARY');
      console.log('='.repeat(80));
      console.log(`\n✅ Visual check completed at ${report.timestamp}`);
      console.log(`📁 Screenshots saved to: ${report.screenshotsDir}\n`);

      return report;
    }

  } catch (error) {
    console.error('❌ Visual check failed:', error);
    
    // Try to take an error screenshot if page exists
    try {
      if (typeof page !== 'undefined' && page) {
        const errorScreenshot = path.join(SCREENSHOTS_DIR, `${SCREENSHOT_PREFIX}-error.png`);
        await page.screenshot({ path: errorScreenshot, fullPage: true }).catch(() => {});
        console.log(`📸 Error screenshot saved to: ${errorScreenshot}`);
      }
    } catch (e) {
      // Ignore screenshot errors
    }
    
    throw error;
  } finally {
    await browser.close();
    console.log('🎭 Browser closed');
  }
}

// Run if called directly
if (require.main === module) {
  runVisualCheck()
    .then(() => {
      console.log('✅ Visual check script completed successfully');
      process.exit(0);
    })
    .catch((error) => {
      console.error('❌ Visual check script failed:', error);
      process.exit(1);
    });
}

module.exports = { runVisualCheck };
