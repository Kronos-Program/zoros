import { defineConfig } from '@playwright/test';

export default defineConfig({
  webServer: {
    command: 'npm run start',
    port: 8888,
    timeout: 120 * 1000,
    reuseExistingServer: true,
  },
  testDir: './tests',
});
