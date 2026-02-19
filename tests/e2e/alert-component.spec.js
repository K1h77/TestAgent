const { test, expect } = require('@playwright/test');

test.describe('Alert Component', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
    // Login to access the main UI
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    // Wait for main UI to load
    await page.waitForSelector('#mainContainer', { state: 'visible' });
  });

  test('should display success alert when triggered', async ({ page }) => {
    // Initially, no alert should be visible
    const alertContainer = page.locator('.alert-container');
    await expect(alertContainer).not.toBeVisible();
    
    // Trigger a success alert (we'll need to add this functionality)
    await page.evaluate(() => {
      // This will fail initially - we need to implement showAlert function
      window.showAlert('Task added successfully!', 'success');
    });
    
    // After triggering, alert should be visible
    await expect(alertContainer).toBeVisible();
    
    // Should have success styling
    const successAlert = page.locator('.alert.alert-success');
    await expect(successAlert).toBeVisible();
    
    // Should contain the message
    await expect(successAlert).toContainText('Task added successfully!');
    
    // Should have close button
    const closeButton = successAlert.locator('.alert-close');
    await expect(closeButton).toBeVisible();
  });

  test('should display error alert when triggered', async ({ page }) => {
    // Trigger an error alert
    await page.evaluate(() => {
      window.showAlert('Failed to add task', 'error');
    });
    
    const errorAlert = page.locator('.alert.alert-error');
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText('Failed to add task');
    await expect(errorAlert.locator('.alert-close')).toBeVisible();
  });

  test('should display info alert when triggered', async ({ page }) => {
    // Trigger an info alert
    await page.evaluate(() => {
      window.showAlert('Task updated', 'info');
    });
    
    const infoAlert = page.locator('.alert.alert-info');
    await expect(infoAlert).toBeVisible();
    await expect(infoAlert).toContainText('Task updated');
    await expect(infoAlert.locator('.alert-close')).toBeVisible();
  });

  test('should close alert when close button is clicked', async ({ page }) => {
    // Trigger an alert
    await page.evaluate(() => {
      window.showAlert('Test alert', 'success');
    });
    
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    
    // Click close button
    await alert.locator('.alert-close').click();
    
    // Alert should be hidden
    await expect(alert).not.toBeVisible();
  });

  test('should automatically dismiss alert after timeout', async ({ page }) => {
    // Trigger an alert with auto-dismiss
    await page.evaluate(() => {
      window.showAlert('Auto-dismiss alert', 'info', 1000);
    });
    
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    
    // Wait for auto-dismiss
    await page.waitForTimeout(1500);
    
    // Alert should be hidden
    await expect(alert).not.toBeVisible();
  });

  test('should support multiple alerts stacking', async ({ page }) => {
    // Trigger multiple alerts
    await page.evaluate(() => {
      window.showAlert('First alert', 'success');
      window.showAlert('Second alert', 'error');
      window.showAlert('Third alert', 'info');
    });
    
    const alerts = page.locator('.alert');
    await expect(alerts).toHaveCount(3);
    
    // Check they're stacked in order
    const alertTexts = await alerts.allTextContents();
    expect(alertTexts[0]).toContain('First alert');
    expect(alertTexts[1]).toContain('Second alert');
    expect(alertTexts[2]).toContain('Third alert');
  });

  test('should have appropriate styling for each alert type', async ({ page }) => {
    // Test success alert styling
    await page.evaluate(() => {
      window.showAlert('Success', 'success');
    });
    
    const successAlert = page.locator('.alert.alert-success');
    await expect(successAlert).toBeVisible();
    
    // Test error alert styling
    await page.evaluate(() => {
      window.showAlert('Error', 'error');
    });
    
    const errorAlert = page.locator('.alert.alert-error');
    await expect(errorAlert).toBeVisible();
    
    // Test info alert styling
    await page.evaluate(() => {
      window.showAlert('Info', 'info');
    });
    
    const infoAlert = page.locator('.alert.alert-info');
    await expect(infoAlert).toBeVisible();
  });
});