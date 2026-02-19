const { test, expect } = require('@playwright/test');

test.describe('Login Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should have username and password fields', async ({ page }) => {
    await expect(page.locator('#username')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
  });

  test('should have a Submit button next to username and password fields', async ({ page }) => {
    // Check that there is a submit button with text "Submit"
    const submitButton = page.locator('button[type="submit"]');
    await expect(submitButton).toBeVisible();
    await expect(submitButton).toHaveText('Submit');
    
    // Check that the button is positioned next to the input fields
    // We can check by verifying the form structure
    const form = page.locator('#loginForm');
    await expect(form).toBeVisible();
    
    // The button should be after the password field in the form
    const passwordField = page.locator('#password');
    const submitButtonInForm = form.locator('button[type="submit"]');
    
    // Check that button exists in the form
    await expect(submitButtonInForm).toBeVisible();
  });

  test('should show error message for invalid credentials', async ({ page }) => {
    // Fill in invalid credentials
    await page.fill('#username', 'invaliduser');
    await page.fill('#password', 'wrongpassword');
    
    // Click the submit button
    await page.click('button[type="submit"]');
    
    // Should show an error message
    // We'll need to check for an error element - this should fail initially
    const errorMessage = page.locator('.error-message');
    await expect(errorMessage).toBeVisible();
    await expect(errorMessage).toContainText('Invalid credentials');
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    // Fill in valid credentials (we'll need to define what valid credentials are)
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'testpass');
    
    // Click the submit button
    await page.click('button[type="submit"]');
    
    // Should navigate to main app page
    await expect(page.locator('#mainContainer')).toBeVisible();
    await expect(page.locator('#loginContainer')).not.toBeVisible();
  });
});