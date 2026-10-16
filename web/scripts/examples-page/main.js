// One example of @contraagent/elements alone on a page, for its screenshot
// (`screenshots.mjs`): `?example=<name>` mounts docs/examples/<name>.ts, `&theme=` picks a
// built-in theme. `document.body.dataset.ready` is set once it is mounted.
import { adoptThemes } from '../../packages/elements/src/themes/index.ts';

const modules = import.meta.glob('../../packages/elements/docs/examples/*.ts');
const query = new URLSearchParams(location.search);
document.documentElement.dataset['caTheme'] = query.get('theme') ?? 'contraagent-light';
adoptThemes(document);
const load = modules[`../../packages/elements/docs/examples/${query.get('example')}.ts`];
if (!load) throw new Error(`no example ${query.get('example')}`);
const host = document.getElementById('host');
if (!host) throw new Error('no #host');
(await load()).mount(host);
document.body.dataset['ready'] = '1';
