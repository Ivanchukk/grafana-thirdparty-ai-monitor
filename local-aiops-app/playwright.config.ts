import type { PluginOptions } from '@grafana/plugin-e2e';
import { defineConfig } from '@playwright/test';
import baseConfig from './.config/playwright.config';

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// require('dotenv').config();

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig<PluginOptions>(baseConfig, {
  timeout: 120000,
  expect: { timeout: 30000 },
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: { provisioningRootDir: '..', viewport: { width: 1600, height: 1100 } },
});
