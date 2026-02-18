const { test, expect } = require('@playwright/test');

test.describe('Alert Component', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Login
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    await page.waitForSelector('#mainContainer', { state: 'visible' });
  });

  test('should show success alert when triggered', async ({ page }) => {
    // Trigger success alert via JavaScript
    await page.evaluate(() => {
      window.showAlert('Task added successfully!', 'success');
    });
    
    // Check alert appears
    const alert = page.locator('.alert.success');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('Task added successfully!');
    
    // Check close button exists
    const closeBtn = alert.locator('.alert-close');
    await expect(closeBtn).toBeVisible();
  });

  test('should show error alert when triggered', async ({ page }) => {
    await page.evaluate(() => {
      window.showAlert('Failed to add task', 'error');
    });
    
    const alert = page.locator('.alert.error');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('Failed to add task');
  });

  test('should show info alert when triggered', async ({ page }) => {
    await page.evaluate(() => {
      window.showAlert('Please check your input', 'info');
    });
    
    const alert = page.locator('.alert.info');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('Please check your input');
  });

  test('should dismiss alert when close button is clicked', async ({ page }) => {
    await page.evaluate(() => {
      window.showAlert('Test alert', 'success');
    });
    
    const alert = page.locator('.alert.success');
    await expect(alert).toBeVisible();
    
    // Click close button
    await alert.locator('.alert-close').click();
    
    // Alert should be hidden
    await expect(alert).not.toBeVisible();
  });

  test('should have correct styling for different alert types', async ({ page }) => {
    // Test success styling
    await page.evaluate(() => {
      window.showAlert('Success', 'success');
    });
    const successAlert = page.locator('.alert.success');
    await expect(successAlert).toHaveClass(/success/);
    
    // Test error styling
    await page.evaluate(() => {
      window.showAlert('Error', 'error');
    });
    const errorAlert = page.locator('.alert.error');
    await expect(errorAlert).toHaveClass(/error/);
    
    // Test info styling
    await page.evaluate(() => {
      window.showAlert('Info', 'info');
    });
    const infoAlert = page.locator('.alert.info');
    await expect(infoAlert).toHaveClass(/info/);
  });
});
