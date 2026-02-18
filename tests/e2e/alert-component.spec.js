const { test, expect } = require('@playwright/test');

test.describe('Alert Component', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
    
    // Login to access the main application
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await page.waitForSelector('#mainContainer', { state: 'visible' });
  });

  test('should show success alert when triggered', async ({ page }) => {
    // Test that alert component can be triggered with success status
    // This test should fail initially since alert component doesn't exist
    await page.evaluate(() => {
      // Try to trigger a success alert
      if (window.showAlert) {
        window.showAlert('Task added successfully!', 'success');
      }
    });
    
    // Check if alert element exists with success styling
    const alertElement = await page.locator('.alert.success').first();
    await expect(alertElement).toBeVisible();
    await expect(alertElement).toContainText('Task added successfully!');
    
    // Check if close button exists
    const closeButton = await alertElement.locator('.alert-close');
    await expect(closeButton).toBeVisible();
  });

  test('should show error alert when triggered', async ({ page }) => {
    // Test that alert component can be triggered with error status
    await page.evaluate(() => {
      // Try to trigger an error alert
      if (window.showAlert) {
        window.showAlert('Failed to add task!', 'error');
      }
    });
    
    // Check if alert element exists with error styling
    const alertElement = await page.locator('.alert.error').first();
    await expect(alertElement).toBeVisible();
    await expect(alertElement).toContainText('Failed to add task!');
  });

  test('should show info alert when triggered', async ({ page }) => {
    // Test that alert component can be triggered with info status
    await page.evaluate(() => {
      // Try to trigger an info alert
      if (window.showAlert) {
        window.showAlert('Please fill in all required fields', 'info');
      }
    });
    
    // Check if alert element exists with info styling
    const alertElement = await page.locator('.alert.info').first();
    await expect(alertElement).toBeVisible();
    await expect(alertElement).toContainText('Please fill in all required fields');
  });

  test('should dismiss alert when close button is clicked', async ({ page }) => {
    // Test that alert can be dismissed
    await page.evaluate(() => {
      // Trigger an alert first
      if (window.showAlert) {
        window.showAlert('Test alert', 'success');
      }
    });
    
    const alertElement = await page.locator('.alert.success').first();
    await expect(alertElement).toBeVisible();
    
    // Click the close button
    await alertElement.locator('.alert-close').click();
    
    // Alert should be hidden or removed
    await expect(alertElement).not.toBeVisible();
  });

  test('should automatically dismiss alert after timeout', async ({ page }) => {
    // Test that alert auto-dismisses after timeout
    await page.evaluate(() => {
      // Trigger an alert with auto-dismiss
      if (window.showAlert) {
        window.showAlert('Auto-dismiss alert', 'info', 1000);
      }
    });
    
    const alertElement = await page.locator('.alert.info').first();
    await expect(alertElement).toBeVisible();
    
    // Wait for auto-dismiss
    await page.waitForTimeout(1500);
    
    // Alert should be hidden after timeout
    await expect(alertElement).not.toBeVisible();
  });

  test('should integrate with existing task operations', async ({ page }) => {
    // Test that alert component works with existing functionality
    // Add a task and expect success alert
    await page.fill('#taskTitle', 'Test task with alert');
    await page.fill('#taskDescription', 'Test description');
    
    // Mock the fetch to trigger alert
    await page.evaluate(() => {
      // Override fetch to simulate success and trigger alert
      const originalFetch = window.fetch;
      window.fetch = async function(...args) {
        if (args[0].includes('/api/tasks') && args[1]?.method === 'POST') {
          // Simulate successful response
          const response = new Response(JSON.stringify({
            id: 999,
            title: 'Test task with alert',
            description: 'Test description',
            completed: false
          }), {
            status: 201,
            headers: { 'Content-Type': 'application/json' }
          });
          
          // Trigger success alert
          if (window.showAlert) {
            window.showAlert('Task added successfully!', 'success');
          }
          
          return response;
        }
        return originalFetch.apply(this, args);
      };
    });
    
    await page.click('button:has-text("Add Task")');
    
    // Check if success alert appears
    const alertElement = await page.locator('.alert.success').first();
    await expect(alertElement).toBeVisible();
    await expect(alertElement).toContainText('Task added successfully!');
  });
});