import { test, expect } from '@grafana/plugin-e2e';
import path from 'node:path';
import pluginJson from '../src/plugin.json';

test('app discovers live context, filters nodes, investigates and accepts follow-ups', async ({
  gotoAppPage,
  page,
  readProvisionedDashboard,
}) => {
  await page.setViewportSize({ width: 1600, height: 1100 });
  const dashboard = await readProvisionedDashboard({ fileName: 'elasticsearch.json' });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await gotoAppPage({ pluginId: pluginJson.id, path: `investigate?dashboard=${dashboard.uid}` });
  const app = page.locator('main.aiops');
  await expect(app.getByText('10 panels discovered')).toBeVisible();
  await expect(app.getByText('MOCK AI · DEVELOPMENT', { exact: true })).toBeVisible();
  await app.getByLabel('Node', { exact: true }).selectOption(['es-node-2']);
  await expect(app.getByLabel('Node', { exact: true })).toHaveValues(['es-node-2']);
  await app.getByRole('button', { name: 'Analyze Dashboard' }).click();
  await expect(app.locator('.ai-trace').first()).toBeVisible({ timeout: 30000 });
  await expect(app.locator('.ai-trace').first()).toContainText('7 tool calls');
  await app.locator('.ai-trace > summary').first().click();
  await expect(app.locator('.ai-trace').first()).toContainText('query_panel_data');
  await expect(app.locator('.ai-error')).toHaveCount(0);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.resolve('../artifacts/assistant.png') });
  await app
    .getByRole('textbox', { name: 'Ask a follow-up question' })
    .fill('Which node did you inspect and what should I check next?');
  await app.getByRole('button', { name: 'Send' }).click();
  await expect(app.locator('.ai-assistant')).toHaveCount(2, { timeout: 30000 });
  await expect(app.getByRole('button', { name: 'Start a new investigation' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('provisioned dashboard renders real queries and panel action preserves context', async ({
  gotoDashboardPage,
  page,
  readProvisionedDashboard,
}) => {
  await page.setViewportSize({ width: 1600, height: 1100 });
  const dashboard = await readProvisionedDashboard({ fileName: 'elasticsearch.json' });
  const dashboardPage = await gotoDashboardPage({ uid: dashboard.uid });
  await dashboardPage.waitForPanelsQueriesToComplete({ scrollAll: true, timeout: 30000 });
  const cpu = dashboardPage.getPanelByTitle(dashboard.panels[0].title);
  await cpu.scrollIntoView();
  await expect(cpu.locator).toBeVisible();
  await expect(cpu.getErrorIcon()).not.toBeVisible();
  await expect(cpu.locator).toContainText('es-node-1');
  await page.screenshot({ path: path.resolve('../artifacts/dashboard.png') });
  await cpu.clickOnMenuItem('Analyze with AI', { parentItem: 'Extensions' });
  await expect(page).toHaveURL(new RegExp(`/a/${pluginJson.id}/investigate\\?dashboard=${dashboard.uid}`));
  await expect(page.locator('main.aiops').getByText('10 panels discovered')).toBeVisible();
});
