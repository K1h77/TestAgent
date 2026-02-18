const { test, expect } = require('@playwright/test');

test.describe('Dark Mode Feature', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage before each test
    await page.addInitScript(() => {
      localStorage.clear();
    });
    // Navigate to the app
    await page.goto('/');
  });

  test('should have dark mode toggle in header', async ({ page }) => {
    // Login first
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await expect(page.locator('#mainContainer')).toBeVisible();
    
    // Check that dark mode toggle exists
    const darkModeToggle = page.locator('#darkModeToggle');
    await expect(darkModeToggle).toBeVisible();
    
    // Check the toggle is a checkbox
    await expect(darkModeToggle).toHaveAttribute('type', 'checkbox');
  });

  test('should toggle dark mode when switch is clicked', async ({ page }) => {
    // Login first
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await expect(page.locator('#mainContainer')).toBeVisible();
    
    // Initially body should not have dark-mode class
    await expect(page.locator('body')).not.toHaveClass(/dark-mode/);
    
    // Click the dark mode toggle
    await page.click('#darkModeToggle');
    
    // Now body should have dark-mode class
    await expect(page.locator('body')).toHaveClass(/dark-mode/);
  });

  test('should persist dark mode preference in localStorage', async ({ page }) => {
    // Login first
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await expect(page.locator('#mainContainer')).toBeVisible();
    
    // Click the dark mode toggle
    await page.click('#darkModeToggle');
    
    // Verify localStorage has the dark mode setting
    const darkModeValue = await page.evaluate(() => localStorage.getItem('darkMode'));
    expect(darkModeValue).toBe('enabled');
  });

  test('should restore dark mode preference on page reload', async ({ page }) => {
    // Login first
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await expect(page.locator('#mainContainer')).toBeVisible();
    
    // Enable dark mode
    await page.click('#darkModeToggle');
    await expect(page.locator('body')).toHaveClass(/dark-mode/);
    
    // Reload the page
    await page.reload();
    
    // Login again
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container
    await expect(page.locator('#mainContainer')).toBeVisible();
    
    // Dark mode should still be enabled
    await expect(page.locator('body')).toHaveClass(/dark-mode/);
    await expect(page.locator('#darkModeToggle')).toBeChecked();
  });
});
