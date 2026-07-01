/**
 * theme.js
 * --------
 * Theme management for DoubtNet. Cycles through available themes,
 * persists choice in localStorage.
 */

const Theme = (() => {
  const THEMES = ['dark', 'light', 'cyber', 'midnight'];

  function getCurrent() {
    return localStorage.getItem('doubtnet-theme') || 'dark';
  }

  function apply(name) {
    document.documentElement.setAttribute('data-theme', name);
    localStorage.setItem('doubtnet-theme', name);

    const btn = document.querySelector('.theme-btn');
    if (btn) {
      btn.textContent = name.charAt(0).toUpperCase() + name.slice(1);
    }
  }

  function cycle() {
    const current = getCurrent();
    const idx = THEMES.indexOf(current);
    const next = THEMES[(idx + 1) % THEMES.length];
    apply(next);
  }

  function init() {
    apply(getCurrent());

    document.addEventListener('click', (e) => {
      if (e.target.closest('.theme-btn')) {
        cycle();
      }
    });
  }

  return { init, cycle, apply, getCurrent, THEMES };
})();
