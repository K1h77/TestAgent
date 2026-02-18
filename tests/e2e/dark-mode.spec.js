const { test, expect } = require('@playwright/test');

test.describe('Dark Mode Switch', () => {
  test('should have a dark mode switch in the top right corner', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
    
    // Login with any credentials
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Check for dark mode switch in the header
    const header = page.locator('.header');
    await expect(header).toBeVisible();
    
    // Look for dark mode switch container
    const darkModeSwitch = page.locator('.dark-mode-switch');
    await expect(darkModeSwitch).toBeVisible();
    
    // Check for the toggle label (the visible part)
    const darkModeLabel = page.locator('.dark-mode-label');
    await expect(darkModeLabel).toBeVisible();
    
    // Check for the toggle checkbox (it's hidden but should exist)
    const darkModeToggle = page.locator('#darkModeToggle');
    await expect(darkModeToggle).toHaveCount(1);
  });

  test('should toggle dark mode when switch is clicked', async ({ page }) => {
    // Navigate and login
    await page.goto('/');
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Find dark mode label (the visible part)
    const darkModeLabel = page.locator('.dark-mode-label');
    const darkModeToggle = page.locator('#darkModeToggle');
    
    // Check initial state - should be light mode
    const body = page.locator('body');
    await expect(body).not.toHaveClass(/dark-mode/);
    await expect(darkModeToggle).not.toBeChecked();
    
    // Click the label to toggle dark mode
    await darkModeLabel.click();
    
    // Should now have dark mode class
    await expect(body).toHaveClass(/dark-mode/);
    await expect(darkModeToggle).toBeChecked();
    
    // Click again to toggle back
    await darkModeLabel.click();
    
    // Should be back to light mode
    await expect(body).not.toHaveClass(/dark-mode/);
    await expect(darkModeToggle).not.toBeChecked();
  });

  test('should persist dark mode preference', async ({ page }) => {
    // Navigate and login
    await page.goto('/');
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Enable dark mode by clicking the label
    const darkModeLabel = page.locator('.dark-mode-label');
    const darkModeToggle = page.locator('#darkModeToggle');
    await darkModeLabel.click();
    
    // Verify dark mode is enabled
    const body = page.locator('body');
    await expect(body).toHaveClass(/dark-mode/);
    
    // Verify checkbox is checked
    await expect(darkModeToggle).toBeChecked();
    
    // Refresh page
    await page.reload();
    
    // Login again after reload
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    
    // Wait for main container again
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Dark mode should still be enabled
    await expect(body).toHaveClass(/dark-mode/);
    
    // Switch should still be checked
    await expect(darkModeToggle).toBeChecked();
  });
});