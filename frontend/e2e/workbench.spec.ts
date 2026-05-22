import { expect, test } from '@playwright/test';
import path from 'node:path';

const sampleMesh = path.resolve('../samples/wing.msh');

test('runs fake-mode external-aero workflow from upload to dashboard artifacts', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'AI CFD Workbench' })).toBeVisible();
  await expect(page.getByText('Drop STEP, STL, Gmsh mesh, or OpenFOAM ZIP')).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(sampleMesh);
  await expect(page.getByText('wing.msh')).toBeVisible();

  await page.getByLabel('Velocity').fill('31.5');
  await page.getByLabel('Angle of attack').fill('5');
  await page.getByRole('button', { name: /Start CFD run/i }).click();

  await expect(page.getByText('Completed').first()).toBeVisible();
  await expect(page.getByText('pressure.png')).toBeVisible();
  await page.getByRole('button', { name: 'Inspect pressure.png' }).click();
  await expect(page.getByRole('dialog', { name: 'pressure.png preview' })).toBeVisible();
  await page.getByRole('button', { name: 'Close visual preview' }).click();
  await expect(page.getByText('solver.log')).toBeVisible();
  await expect(page.getByText(/Fake OpenFOAM solver completed/i)).toBeVisible();
});
