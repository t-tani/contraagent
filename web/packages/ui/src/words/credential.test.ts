import { describe, expect, it } from 'vitest';
import { credentialLabel, credentialTip } from './credential.js';

describe('credential', () => {
  it('shows the built-in credential as default, with local credentials in its tooltip', () => {
    expect([credentialLabel('ambient'), credentialLabel('team-key'), credentialLabel('')]).toEqual(['default', 'team-key', '']);
    expect([credentialTip('ambient'), credentialTip('team-key')]).toEqual(['local credentials (ambient)', '']);
  });
});
