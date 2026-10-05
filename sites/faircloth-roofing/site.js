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

  const yr = document.getElementById('yr');
  if (yr) yr.textContent = new Date().getFullYear();
})();
