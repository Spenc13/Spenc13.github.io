// Shared behavior for the service pages. Uses the same storage key as the home
// page, so a theme picked on one page carries over to the others.
(function () {
  const btn = document.getElementById('themeBtn'), root = document.documentElement, modes = ['system', 'light', 'dark'];
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
})();
document.querySelectorAll('.menu .panel a').forEach(a => a.addEventListener('click', () => a.closest('details').open = false));
document.getElementById('yr').textContent = new Date().getFullYear();
