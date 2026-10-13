// A credential as the reader knows it (shown as "identity").
import { msg } from '@lit/localize';

/** A credential as the reader knows it: the built-in `ambient` shows as "default". */
export const credentialLabel = (c: string | null | undefined): string => (!c ? '' : c === 'ambient' ? msg('default') : c);

/** What a credential's label leaves out, for its tooltip: the built-in `ambient` is the local credentials. */
export const credentialTip = (c: string | null | undefined): string => (c === 'ambient' ? msg('local credentials (ambient)') : '');
