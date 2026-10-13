// A segmented control: one choice among a few. The host holds the value and
// answers `cae-change`; the words are the host's.
import '@contraagent/elements/segmented/define';

export function mount(host: HTMLElement): void {
  const control = document.createElement('cae-segmented');
  control.label = 'Period';
  control.options = [
    { value: 'day', label: 'Day' },
    { value: 'week', label: 'Week' },
    { value: 'month', label: 'Month', title: 'The last 30 days' },
  ];
  control.value = 'week';
  const shown = document.createElement('p');
  shown.textContent = `Showing: ${control.value}`;
  control.addEventListener('cae-change', (e) => (shown.textContent = `Showing: ${e.detail.value}`));
  host.replaceChildren(control, shown);
}
