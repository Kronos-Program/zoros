import { test, expect } from '@playwright/test';

test('record buttons trigger endpoints', async ({ page }) => {
  await page.goto('http://localhost:8888');
  const [req] = await Promise.all([
    page.waitForRequest('**/api/dictate/start'),
    page.click('text=Start Recording'),
  ]);
  expect(req.method()).toBe('POST');
});
