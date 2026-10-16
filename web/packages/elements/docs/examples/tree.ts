// A tree of a CI pipeline's files, paired with a code element: selecting a file shows
// its text. The host holds the selection and answers `cae-select`.
import '@contraagent/elements/code/define';
import '@contraagent/elements/tree/define';
import type { TreeItem } from '@contraagent/elements/tree';

const files: Record<string, string> = {
  'ci/build.py': 'def build(target: str) -> bool:\n    return run(["make", target]).returncode == 0\n',
  'ci/jobs.yaml': 'jobs:\n  unit: { needs: [build] }\n  lint: { needs: [] }\n',
  'ci/tests/test_build.py': 'def test_build():\n    assert build("all")\n',
  'README.md': 'The CI pipeline of the project.\n',
};

const items: TreeItem[] = [
  {
    id: 'ci',
    name: 'ci',
    children: [
      { id: 'ci/build.py', name: 'build.py' },
      { id: 'ci/jobs.yaml', name: 'jobs.yaml', badge: 'changed', tone: 'attention' },
      { id: 'ci/tests', name: 'tests', open: false, children: [{ id: 'ci/tests/test_build.py', name: 'test_build.py', badge: 'failed', tone: 'failed' }] },
    ],
  },
  { id: 'README.md', name: 'README.md' },
];

export function mount(host: HTMLElement): void {
  const tree = document.createElement('cae-tree');
  tree.items = items;
  tree.label = 'Files';
  const code = document.createElement('cae-code');
  const show = (id: string) => {
    tree.selected = id;
    code.code = files[id] ?? '';
    code.path = id;
    code.language = id;
  };
  tree.addEventListener('cae-select', (e) => e.detail.id && show(e.detail.id));
  show('ci/build.py');
  const pair = document.createElement('div');
  pair.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; align-items: start';
  pair.append(tree, code);
  host.replaceChildren(pair);
}
