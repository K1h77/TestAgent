const { test, expect } = require('@playwright/test');

test('debug dark mode', async ({ page }) => {
  await page.goto('/');
  console.log('Page loaded');
  
  // Login
  await page.fill('#username', 'testuser');
  await page.fill('#password', 'testpass');
  await page.click('button[type="submit"]');
  
  console.log('Login submitted');
  
  // Wait for main container
  await page.waitForSelector('#mainContainer', { state: 'visible' });
  console.log('Main container visible');
  
  // Check for dark mode elements
  const darkModeSwitch = await page.locator('.dark-mode-switch').count();
  const darkModeLabel = await page.locator('.dark-mode-label').count();
  const darkModeToggle = await page.locator('#darkModeToggle').count();
  
  console.log(`darkModeSwitch count: ${darkModeSwitch}`);
  console.log(`darkModeLabel count: ${darkModeLabel}`);
  console.log(`darkModeToggle count: ${darkModeToggle}`);
  
  // Take a screenshot
  await page.screenshot({ path: 'debug.png' });
  
  // Check body classes
  const bodyClasses = await page.locator('body').getAttribute('class');
  console.log(`Body classes: ${bodyClasses}`);
  
  // Try to click the label
  const label = page.locator('.dark-mode-label');
  await label.click();
  console.log('Label clicked');
  
  // Check body classes again
  const newBodyClasses = await page.locator('body').getAttribute('class');
  console.log(`New body classes: ${newBodyClasses}`);
  
  // Check if checkbox is checked
  const isChecked = await page.locator('#darkModeToggle').isChecked();
  console.log(`Checkbox checked: ${isChecked}`);
});