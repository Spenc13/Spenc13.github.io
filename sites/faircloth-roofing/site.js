// Shared by every Faircloth Roofing page: theme toggle, menus, footer year.
(function () {
  const root = document.documentElement, btn = document.getElementById('themeBtn'), modes = ['system', 'light', 'dark'];
  let mode = 'system';
  try { mode = localStorage.getItem('fr-theme') || 'system'; } catch (e) {}
  const apply = () => {
    if (mode === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', mode);
    btn.setAttribute('aria-label', 'Color theme: ' + mode + '. Click to change.');
    btn.title = 'Theme: ' + mode;
  };
  apply();
  btn.addEventListener('click', () => {
    mode = modes[(modes.indexOf(mode) + 1) % 3];
    try { localStorage.setItem('fr-theme', mode); } catch (e) {}
    apply();
  });

  // Mobile menu: close after picking a link, and on Escape.
  const menu = document.querySelector('.menu');
  menu.querySelectorAll('.panel a').forEach(a => a.addEventListener('click', () => { menu.open = false; }));
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (menu.open) { menu.open = false; menu.querySelector('summary').focus(); }
    // Desktop dropdowns open on hover/focus; Escape moves focus out so they close.
    const dd = document.activeElement && document.activeElement.closest('.dd');
    if (dd) { dd.querySelector('a').focus(); dd.querySelector('a').blur(); }
  });

  // Open every page at the top. Some viewers (and embedded previews) carry the
  // previous page's scroll position over; Back/Forward and #section links keep theirs.
  const nav = performance.getEntriesByType && performance.getEntriesByType('navigation')[0];
  const toTop = () => {
    if (location.hash || (nav && nav.type === 'back_forward')) return;
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  };
  toTop();
  addEventListener('load', toTop, { once: true });
  addEventListener('pageshow', e => { if (!e.persisted) toTop(); });

  const yr = document.getElementById('yr');
  if (yr) yr.textContent = new Date().getFullYear();
})();
