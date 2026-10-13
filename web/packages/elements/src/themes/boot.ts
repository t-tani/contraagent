// The page's theme before the first paint.
import { THEME_STORE_KEY } from './choice.js';
import { DEFAULT_THEME, SYSTEM_THEMES, THEME_CHOICES, THEME_NAMES } from './data.js';

/**
 * A script for a page's `<head>`: it sets `data-ca-theme` on `<html>` from the
 * reader's choice before the first paint, as `resolveTheme(preferredTheme(), prefersLight())`
 * does. With `themeRules` in a `<style>` beside it, the page opens in its theme.
 */
export const themeBootScript = `(function(){var c=null;try{c=localStorage.getItem(${JSON.stringify(THEME_STORE_KEY)})}catch(e){}
var names=${JSON.stringify(THEME_NAMES)},choices=${JSON.stringify(THEME_CHOICES)};
if(choices.indexOf(c)<0)c=${JSON.stringify(DEFAULT_THEME)};
if(c==="system")c=window.matchMedia&&matchMedia("(prefers-color-scheme: light)").matches?${JSON.stringify(SYSTEM_THEMES.light)}:${JSON.stringify(SYSTEM_THEMES.dark)};
if(names.indexOf(c)>=0)document.documentElement.setAttribute("data-ca-theme",c);})();`;
