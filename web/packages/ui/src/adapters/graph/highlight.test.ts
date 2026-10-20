import { describe, expect, it } from 'vitest';
import { related, taskLinks } from './highlight.js';
import { node } from './plans.fixture.js';

describe('related', () => {
  it('lights the tasks joined to a unit, each by the weakest link of its strongest path', () => {
    const nodes = [
      node('prepare-u', 'u', 'prepare', 'done'),
      node('summarize-u', 'u', 'summarize', 'done', { given_from: ['prepare-u'], after: ['prepare-u'] }),
      // given u's summary: data
      node('report', '', 'report', 'done', { given_from: ['summarize-u'] }),
      // waits for the report only: order, though the report is data
      node('publish', '', 'publish', 'pending', { after: ['report'] }),
      // created after the report's result
      node('notify', '', 'notify', 'pending', { created_from: ['report'] }),
      // given the report's output, and also reached by order: data wins
      node('archive', '', 'archive', 'pending', { given_from: ['report'], after: ['publish'] }),
      node('other-v', 'v', 'other', 'done'),
    ];
    const on = related(nodes, taskLinks(nodes), 'u');
    expect(Object.fromEntries(on)).toEqual({
      'prepare-u': null,
      'summarize-u': null,
      report: 'given',
      publish: 'after',
      notify: 'created',
      archive: 'given',
    });
  });
});
