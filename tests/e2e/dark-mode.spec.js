const { test, expect } = require('@playwright/test');

test.describe('Dark Mode Switch', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Login
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    await expect(page.locator('#mainContainer')).toBeVisible();
  });

  test('should have a dark mode switch in the top right corner', async ({ page }) => {
    // Check that a dark mode switch exists
    const darkModeSwitch = page.locator('.dark-mode-switch');
    await expect(darkModeSwitch).toBeVisible();
    
    // Verify it's in the top right corner (near header)
    const header = page.locator('.header');
    const headerBox = await header.boundingBox();
    const switchBox = await darkModeSwitch.boundingBox();
    expect(switchBox.y).toBeLessThan(headerBox.y + headerBox.height + 50);
    expect(switchBox.x).toBeGreaterThan(headerBox.x + headerBox.width - 200);
  });

  test('should toggle dark mode when clicked', async ({ page }) => {
    const darkModeSwitch = page.locator('.dark-mode-switch');
    
    // Initially should not have dark mode class
    await expect(page.locator('body')).not.toHaveClass(/dark-mode/);
    
    // Click the switch
    await darkModeSwitch.click();
    
    // Should now have dark mode class
    await expect(page.locator('body')).toHaveClass(/dark-mode/);
    
    // Click again to toggle off
    await darkModeSwitch.click();
    await expect(page.locator('body')).not.toHaveClass(/dark-mode/);
  });

  test('should persist dark mode preference', async ({ page }) => {
    const darkModeSwitch = page.locator('.dark-mode-switch');
    
    // Enable dark mode
    await darkModeSwitch.click();
    await expect(page.locator('body')).toHaveClass(/dark-mode/);
    
    // Refresh page
    await page.reload();
    
    // Dark mode should still be enabled
    await expect(page.locator('body')).toHaveClass(/dark-mode/);
  });

  test('should apply dark mode styles', async ({ page }) => {
    const darkModeSwitch = page.locator('.dark-mode-switch');
    
    // Enable dark mode
    await darkModeSwitch.click();
    
    // Check that dark mode class is applied
    await expect(page.locator('body')).toHaveClass(/dark-mode/);
    
    // Check that container has dark mode styles applied
    const container = page.locator('.container');
    await expect(container).toHaveCSS('background-color', /rgb\(15, 52, 96\)|rgba\(15, 52, 96/);
  });
});