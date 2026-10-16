// The elements of the two web packages, from the custom elements manifests their
// builds write (custom-elements.json), and where the site documents each one.
import { repoJson } from './repo';
import { withBase } from './base';

export interface Member { kind: string; name: string; privacy?: string; static?: boolean; type?: { text: string }; description?: string; attribute?: string; default?: string; readonly?: boolean }
export interface Ev { name: string; description?: string }
export interface Part { name: string; description?: string }
export interface Decl { kind: string; name: string; tagName?: string; description?: string; members?: Member[]; events?: Ev[]; cssParts?: Part[]; path: string }
interface Manifest { modules: { path: string; declarations?: Omit<Decl, 'path'>[] }[] }

/** Each package with elements: its name, its manifest and its reference page. */
export const PACKAGES = {
  ui: { name: '@contraagent/ui', manifest: 'web/packages/ui/custom-elements.json', reference: '/reference/ui/' },
  elements: { name: '@contraagent/elements', manifest: 'web/packages/elements/custom-elements.json', reference: '/reference/elements/' },
} as const;
export type PackageKey = keyof typeof PACKAGES;

/** Elements that only another element renders: no entry of their own. */
const INTERNAL = new Set(['ca-clock']);

/** A package's elements with a tag, by tag. */
export function elementsOf(pkg: PackageKey): Decl[] {
  return repoJson<Manifest>(PACKAGES[pkg].manifest)
    .modules.flatMap((m) => (m.declarations ?? []).map((d) => ({ ...d, path: m.path })))
    .filter((d) => d.tagName && !INTERNAL.has(d.tagName))
    .sort((a, b) => a.tagName!.localeCompare(b.tagName!));
}

/** The package a tag belongs to. */
export const packageOf = (tag: string): PackageKey => (tag.startsWith('cae-') ? 'elements' : 'ui');

/** An element's entry in the reference. */
export const referenceUrl = (tag: string): string => withBase(`${PACKAGES[packageOf(tag)].reference}#${tag}`);

/** The elements the gallery (src/content/docs/elements.mdx) shows under a heading of their tag. */
export const GALLERY = new Set([
  'ca-monitor', 'ca-task-view', 'ca-definitions', 'ca-pipeline-graph', 'ca-transcript', 'ca-timeline', 'ca-kpis', 'ca-journal-table', 'ca-task-table', 'ca-contracts', 'ca-panel-body',
  'cae-data-table', 'cae-layered-graph', 'cae-mark-matrix', 'cae-stat-tiles', 'cae-lanes', 'cae-check-table', 'cae-transcript', 'cae-code', 'cae-tree', 'cae-segmented',
]);

/** An element's own description (its JSDoc). */
export const describe = (tag: string): string | undefined => elementsOf(packageOf(tag)).find((d) => d.tagName === tag)?.description;
