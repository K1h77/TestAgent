const { test, expect } = require('@playwright/test');

test.describe('Alert Component', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Login to access the main app
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    await page.waitForSelector('#mainContainer', { state: 'visible' });
  });

  test('should show success alert when triggered', async ({ page }) => {
    // Test that alert component exists
    const alertContainer = page.locator('.alert-container');
    await expect(alertContainer).not.toBeVisible();
    
    // Trigger a success alert (we'll need to implement this)
    await page.evaluate(() => {
      window.showAlert('Task added successfully!', 'success');
    });
    
    // Check if alert appears
    await expect(alertContainer).toBeVisible();
    
    // Check alert content and styling
    const alert = page.locator('.alert');
    await expect(alert).toHaveClass(/alert-success/);
    await expect(alert).toContainText('Task added successfully!');
  });

  test('should show error alert when triggered', async ({ page }) => {
    // Trigger an error alert
    await page.evaluate(() => {
      window.showAlert('Failed to add task', 'error');
    });
    
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    await expect(alert).toHaveClass(/alert-error/);
    await expect(alert).toContainText('Failed to add task');
  });

  test('should show info alert when triggered', async ({ page }) => {
    // Trigger an info alert
    await page.evaluate(() => {
      window.showAlert('Task updated', 'info');
    });
    
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    await expect(alert).toHaveClass(/alert-info/);
    await expect(alert).toContainText('Task updated');
  });

  test('should support different statuses (success, error, info)', async ({ page }) => {
    // Test all status types
    const statuses = ['success', 'error', 'info'];
    
    for (const status of statuses) {
      await page.evaluate((status) => {
        window.showAlert(`Test ${status} alert`, status);
      }, status);
      
      const alert = page.locator('.alert');
      await expect(alert).toBeVisible();
      await expect(alert).toHaveClass(new RegExp(`alert-${status}`));
      await expect(alert).toContainText(`Test ${status} alert`);
      
      // Close alert before next test
      await page.click('.alert-close');
      await expect(alert).not.toBeVisible();
    }
  });

  test('should have close/dismiss functionality', async ({ page }) => {
    // Show alert
    await page.evaluate(() => {
      window.showAlert('Test alert', 'success');
    });
    
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    
    // Close alert
    await page.click('.alert-close');
    await expect(alert).not.toBeVisible();
  });

  test('should auto-dismiss after timeout', async ({ page }) => {
    // Show alert with auto-dismiss
    await page.evaluate(() => {
      window.showAlert('Auto-dismiss alert', 'info', 1000);
    });
    
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    
    // Wait for auto-dismiss
    await page.waitForTimeout(1500);
    await expect(alert).not.toBeVisible();
  });

  test('should be triggered from parent components', async ({ page }) => {
    // Test that alert can be triggered from existing UI components
    // Add a task to trigger success alert
    await page.fill('#taskTitle', 'Test Task');
    await page.click('button[onclick="addTask()"]');
    
    // Check if alert appears (implementation will add this)
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    await expect(alert).toHaveClass(/alert-success/);
    await expect(alert).toContainText(/Task.*added|success/i);
  });

  test('should have styling that fits application theme', async ({ page }) => {
    // Show alert to check styling
    await page.evaluate(() => {
      window.showAlert('Test styling', 'success');
    });
    
    const alert = page.locator('.alert');
    await expect(alert).toBeVisible();
    
    // Wait a bit for the animation to complete
    await page.waitForTimeout(100);
    
    // Check that alert has correct classes (this validates styling)
    await expect(alert).toHaveClass(/alert-success/);
    
    // Check border radius matches theme (should have some border radius)
    const borderRadius = await alert.evaluate((el) => {
      return window.getComputedStyle(el).borderRadius;
    });
    expect(borderRadius).toMatch(/px/);
    
    // Check box-shadow exists (from CSS)
    const boxShadow = await alert.evaluate((el) => {
      return window.getComputedStyle(el).boxShadow;
    });
    expect(boxShadow).not.toBe('none');
    
    // Check padding exists (from CSS)
    const padding = await alert.evaluate((el) => {
      return window.getComputedStyle(el).padding;
    });
    expect(padding).not.toBe('0px');
    
    // Check that alert has border-left styling (from CSS classes)
    const borderLeftWidth = await alert.evaluate((el) => {
      return window.getComputedStyle(el).borderLeftWidth;
    });
    expect(borderLeftWidth).not.toBe('0px');
  });
});