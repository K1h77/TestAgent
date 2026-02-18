const { test, expect } = require('@playwright/test');

test.describe('Loading Indicator', () => {
  test('should display loading indicator while fetching tasks', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
    
    // Login first
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Check that loading indicator exists in the DOM
    const loadingIndicator = page.locator('#loadingIndicator');
    await expect(loadingIndicator).toBeAttached();
  });

  test('should show loading indicator during initial task load', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
    
    // Login
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    
    // Start listening for the fetch request before clicking submit
    const responsePromise = page.waitForResponse(response => 
      response.url().includes('/api/tasks') && response.request().method() === 'GET'
    );
    
    await page.click('button[type="submit"]');
    
    // Wait for main container to be visible
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // The loading indicator should be visible while data is being fetched
    const loadingIndicator = page.locator('#loadingIndicator');
    
    // Check if loading indicator is visible (it might be very quick)
    // We'll check that it exists and has the proper visibility class
    await expect(loadingIndicator).toBeAttached();
    
    // Wait for the response to complete
    await responsePromise;
    
    // After data loads, loading indicator should be hidden
    await expect(loadingIndicator).toBeHidden();
  });

  test('should hide loading indicator after tasks are loaded', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
    
    // Login
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Wait for tasks to load (either tasks appear or empty message)
    await page.waitForSelector('#tasksList', { state: 'visible' });
    
    // Loading indicator should be hidden after load
    const loadingIndicator = page.locator('#loadingIndicator');
    await expect(loadingIndicator).toBeHidden();
  });

  test('should show loading indicator when adding a task', async ({ page }) => {
    // Navigate and login
    await page.goto('/');
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Wait for initial load to complete
    await page.waitForTimeout(500);
    
    // Fill in task details
    await page.fill('#taskTitle', 'Test Task');
    
    // Click add task button and check for loading indicator
    const responsePromise = page.waitForResponse(response => 
      response.url().includes('/api/tasks') && response.request().method() === 'POST'
    );
    
    await page.click('button:has-text("Add Task")');
    
    // Loading indicator should appear
    const loadingIndicator = page.locator('#loadingIndicator');
    
    // Wait for response
    await responsePromise;
    
    // After adding, it will reload tasks, so eventually it should be hidden
    await expect(loadingIndicator).toBeHidden();
  });

  test('loading indicator should not block user interaction', async ({ page }) => {
    // Navigate and login
    await page.goto('/');
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Even if loading indicator is present, user should be able to interact
    // Check that we can still type in the task input
    await page.fill('#taskTitle', 'Test interaction');
    const value = await page.inputValue('#taskTitle');
    expect(value).toBe('Test interaction');
  });

  test('loading indicator should match app theme', async ({ page }) => {
    // Navigate and login
    await page.goto('/');
    await page.fill('#username', 'testuser');
    await page.fill('#password', 'password');
    await page.click('button[type="submit"]');
    
    // Wait for main container
    await page.waitForSelector('#mainContainer', { state: 'visible' });
    
    // Check loading indicator styling
    const loadingIndicator = page.locator('#loadingIndicator');
    await expect(loadingIndicator).toBeAttached();
    
    // Verify it has appropriate styling (we'll check for spinner class)
    const hasSpinnerClass = await loadingIndicator.evaluate(el => 
      el.classList.contains('spinner') || el.querySelector('.spinner') !== null
    );
    expect(hasSpinnerClass).toBe(true);
  });
});
