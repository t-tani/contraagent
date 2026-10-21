// The tree and the code of the documentation site's gallery (apps/docs/dist, built by
// `pnpm build`): `<cae-tree>` is reached and worked with the keyboard alone, and a
// panel body's tree shows each selected file's code beside it, with no request.
import { expect, test, type Locator, type Page } from '@playwright/test';
import { DOCS } from './docs-site.js';

async function gallery(page: Page): Promise<void> {
  await page.goto(`${DOCS}/elements/`);
  await page.waitForLoadState('networkidle');
}

/** The tree item that has the focus, by its id. */
const focusedId = (tree: Locator) => tree.evaluate((el) => (el.shadowRoot?.activeElement as HTMLElement | null)?.dataset['id'] ?? null);

test('a tree is one tab stop worked with the arrow keys, Enter selects a file and its code shows beside it', async ({ page }) => {
  await gallery(page);
  const figure = page.locator('[data-cae-example="tree"]');
  const tree = figure.locator('cae-tree');
  const code = figure.locator('cae-code');
  await expect(tree.getByRole('treeitem', { name: /build\.py/ }).first()).toHaveAttribute('aria-selected', 'true');
  await expect(tree.locator('[role=treeitem][tabindex="0"]')).toHaveCount(1);

  await tree.getByRole('treeitem', { name: /build\.py/ }).first().focus();
  await page.keyboard.press('ArrowUp');
  await expect.poll(() => focusedId(tree)).toBe('ci');
  await page.keyboard.press('ArrowLeft'); // closes ci
  await expect(tree.locator('[data-id="ci"]')).toHaveAttribute('aria-expanded', 'false');
  await expect(tree.locator('[data-id="ci/build.py"]')).toHaveCount(0);
  await page.keyboard.press('ArrowRight'); // opens it again
  await page.keyboard.press('ArrowRight'); // to its first child
  await expect.poll(() => focusedId(tree)).toBe('ci/build.py');
  await page.keyboard.press('End');
  await expect.poll(() => focusedId(tree)).toBe('README.md');
  await page.keyboard.press('ArrowUp'); // tests, folded
  await expect(tree.locator('[data-id="ci/tests"]')).toHaveAttribute('aria-expanded', 'false');
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowDown');
  await expect.poll(() => focusedId(tree)).toBe('ci/tests/test_build.py');
  await page.keyboard.press('Enter');
  await expect(tree.locator('[data-id="ci/tests/test_build.py"]')).toHaveAttribute('aria-selected', 'true');
  await expect(code.locator('.path')).toHaveText('ci/tests/test_build.py');
  await expect(code.locator('.ln').first()).toHaveText('def test_build():');

  // Tab leaves the tree: it is one tab stop.
  await page.keyboard.press('Tab');
  await expect.poll(() => focusedId(tree)).toBeNull();
});

test("a panel body's tree shows the selected file's code beside it, and another file's when it is selected, with no request", async ({ page }) => {
  await gallery(page);
  const body = page.locator('ca-panel-body');
  const tree = body.locator('cae-tree');
  const code = body.locator('cae-code');
  const selected = tree.locator('[role=treeitem][aria-selected="true"]');
  await expect(selected).toHaveCount(1);
  const firstId = (await selected.getAttribute('data-id')) ?? '';
  // The code beside it shows the selected file once it has drawn.
  await expect(code.locator('.path')).toHaveText(/^out\/.+\.json$/);
  const firstPath = (await code.locator('.path').textContent()) ?? '';

  const requests: string[] = [];
  page.on('request', (r) => requests.push(r.url()));
  await tree.locator(`[data-id="${firstId}"]`).focus();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await expect(selected).not.toHaveAttribute('data-id', firstId);
  await expect(code.locator('.path')).not.toHaveText(firstPath);
  await expect(code.locator('.ln').first()).toContainText('{');
  await tree.locator('[role=treeitem][aria-selected="false"]').first().click();
  await expect(code.locator('.ln')).not.toHaveCount(0);
  expect(requests).toEqual([]);
});
