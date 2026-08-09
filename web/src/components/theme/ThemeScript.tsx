/**
 * Sets the theme attribute before first paint.
 *
 * This has to be a blocking inline script in <head>. Any React-based approach
 * runs after hydration, which means one frame of the wrong theme — and a
 * white flash on a dark-first product is the most visible bug a visitor can
 * be shown. Dark is the fallback because §7.2 makes it the primary theme.
 */
const script = `
(function () {
  try {
    var stored = localStorage.getItem('loupe-theme');
    var theme = stored === 'light' || stored === 'dark'
      ? stored
      : (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`.trim();

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
