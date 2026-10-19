// The monitor's page once its live feed has replayed. The feed is a stream
// (EventSource), which Playwright's `networkidle` does not wait for: the rows, the
// counts and the problems keep arriving after it.
import { expect, type Page } from '@playwright/test';

/**
 * Resolves once the feed of the run the monitor shows has replayed: its header counts
 * the run's tasks ("5 of 9 tasks done"), which it does only then. `scope` is the
 * monitor's element when the page holds more than one.
 */
export async function feedReady(page: Page, scope = 'ca-monitor'): Promise<void> {
  await expect(page.locator(`${scope} header .runbtn .rs`)).toContainText(/\d+ of \d+ tasks done/);
}
