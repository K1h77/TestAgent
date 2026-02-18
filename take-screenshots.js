const { chromium } = require('@playwright/test');
const fs = require('fs');

async function takeScreenshots() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  try {
    // Go to the app
    await page.goto('http://localhost:3000');
    
    // Login
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Take screenshot of switch (light mode)
    await page.screenshot({ path: 'screenshots/dark_mode_switch_light.png', fullPage: false });
    
    // Take screenshot of the whole page in light mode
    await page.screenshot({ path: 'screenshots/light_mode_full.png', fullPage: true });
    
    // Click the dark mode switch
    const darkModeSwitch = page.locator('.dark-mode-switch');
    await darkModeSwitch.click();
    
    // Wait a bit for transition
    await page.waitForTimeout(500);
    
    // Take screenshot of switch (dark mode)
    await page.screenshot({ path: 'screenshots/dark_mode_switch_dark.png', fullPage: false });
    
    // Take screenshot of the whole page in dark mode  
    await page.screenshot({ path: 'screenshots/dark_mode_full.png', fullPage: true });
    
    console.log('Screenshots taken successfully!');
    console.log('1. screenshots/dark_mode_switch_light.png - Switch in light mode');
    console.log('2. screenshots/light_mode_full.png - Full page in light mode');
    console.log('3. screenshots/dark_mode_switch_dark.png - Switch in dark mode');
    console.log('4. screenshots/dark_mode_full.png - Full page in dark mode');
    
  } catch (error) {
    console.error('Error taking screenshots:', error);
  } finally {
    await browser.close();
  }
}

takeScreenshots();