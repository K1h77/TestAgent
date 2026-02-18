const { test, expect } = require('@playwright/test');

test.describe('Alert Component', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Login to access main app
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    await page.waitForSelector('#mainContainer');
  });

  test('should display success alert when task is added', async ({ page }) => {
    // Add a task
    await page.fill('#taskTitle', 'Test Task');
    await page.click('button:has-text("Add Task")');
    
    // Check for success alert
    const alert = await page.locator('.alert.alert-success');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('Task added successfully');
  });

  test('should display error alert when task title is empty', async ({ page }) => {
    // Try to add task without title
    await page.click('button:has-text("Add Task")');
    
    // Check for error alert
    const alert = await page.locator('.alert.alert-error');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('Please enter a task title');
  });

  test('should display success alert when task is deleted', async ({ page }) => {
    // First add a task
    await page.fill('#taskTitle', 'Task to Delete');
    await page.click('button:has-text("Add Task")');
    await page.waitForTimeout(500);
    
    // Delete the task
    page.on('dialog', dialog => dialog.accept());
    await page.click('.delete-btn');
    
    // Check for success alert with specific text
    const alert = await page.locator('.alert.alert-success:has-text("Task deleted successfully")');
    await expect(alert).toBeVisible();
  });

  test('should display success alert when task is completed', async ({ page }) => {
    // First add a task
    await page.fill('#taskTitle', 'Task to Complete');
    await page.click('button:has-text("Add Task")');
    await page.waitForTimeout(500);
    
    // Complete the task
    await page.click('.complete-btn');
    
    // Check for success alert with specific text
    const alert = await page.locator('.alert.alert-success:has-text("Task updated successfully")');
    await expect(alert).toBeVisible();
  });

  test('should display info alert', async ({ page }) => {
    // Trigger info alert by calling showAlert function directly
    await page.evaluate(() => {
      window.showAlert('This is an info message', 'info');
    });
    
    // Check for info alert
    const alert = await page.locator('.alert.alert-info');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText('This is an info message');
  });

  test('should have close button that dismisses alert', async ({ page }) => {
    // Trigger an alert
    await page.evaluate(() => {
      window.showAlert('Test message', 'success');
    });
    
    // Check alert is visible
    const alert = await page.locator('.alert');
    await expect(alert).toBeVisible();
    
    // Click close button
    const closeBtn = await alert.locator('.alert-close');
    await expect(closeBtn).toBeVisible();
    await closeBtn.click();
    
    // Alert should be hidden
    await expect(alert).not.toBeVisible();
  });

  test('should auto-dismiss alert after timeout', async ({ page }) => {
    // Trigger an alert
    await page.evaluate(() => {
      window.showAlert('Auto dismiss message', 'success');
    });
    
    // Check alert is visible
    const alert = await page.locator('.alert');
    await expect(alert).toBeVisible();
    
    // Wait for auto-dismiss (5 seconds)
    await page.waitForTimeout(5500);
    
    // Alert should be hidden
    await expect(alert).not.toBeVisible();
  });

  test('should support multiple alert types with correct styling', async ({ page }) => {
    // Test success alert
    await page.evaluate(() => {
      window.showAlert('Success message', 'success');
    });
    let alert = await page.locator('.alert.alert-success');
    await expect(alert).toBeVisible();
    await alert.locator('.alert-close').click();
    
    // Test error alert
    await page.evaluate(() => {
      window.showAlert('Error message', 'error');
    });
    alert = await page.locator('.alert.alert-error');
    await expect(alert).toBeVisible();
    await alert.locator('.alert-close').click();
    
    // Test info alert
    await page.evaluate(() => {
      window.showAlert('Info message', 'info');
    });
    alert = await page.locator('.alert.alert-info');
    await expect(alert).toBeVisible();
  });

  test('should display alert container in the DOM', async ({ page }) => {
    const alertContainer = await page.locator('#alertContainer');
    await expect(alertContainer).toBeAttached();
  });
});
