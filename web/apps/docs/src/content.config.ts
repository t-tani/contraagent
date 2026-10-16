import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

/** A live element of a page of the web packages (scripts/collect.py, `LIVE`). */
const live = z.object({
  /** A `ca-*` view fed with the demo run, its properties mapped to the fixture's keys. */
  demo: z.string().optional(),
  props: z.record(z.string(), z.string()).optional(),
  attrs: z.record(z.string(), z.string()).optional(),
  /** `@contraagent/elements`' example `docs/examples/<name>.ts`. */
  example: z.string().optional(),
  /** The screenshot of the page it takes the place of; none: under the title. */
  at: z.string().optional(),
  /** The elements it shows, each linked to its reference. */
  tags: z.array(z.string()),
  height: z.string().optional(),
  theme: z.string().optional(),
  custom: z.string().optional(),
  caption: z.string().optional(),
  /** A page that shows the element alone, on the whole screen, linked under it. */
  full: z.string().optional(),
});

export const collections = {
  docs: defineCollection({ loader: docsLoader(), schema: docsSchema({ extend: z.object({ live: z.array(live).optional() }) }) }),
};
