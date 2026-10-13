// The monitor page: importing the kit registers every element, and index.html
// holds <ca-monitor>. The page sets up the languages and the themes itself (the
// packages do nothing at import). The module also exports the kit, so another
// page can import elements, the client and the store from a running monitor
// (`/app.js`).
import { configureLocales } from '@contraagent/ui/localize';
import { adoptThemes } from '@contraagent/elements/themes';

configureLocales();
adoptThemes(document);

export * from '@contraagent/ui';
export * from '@contraagent/api';
export * as elements from '@contraagent/elements';
