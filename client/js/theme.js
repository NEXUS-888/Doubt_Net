/**
 * theme.js
 * --------
 * Theme management for DoubtNet. Cycles through available themes,
 * persists choice in localStorage.
 */

const Theme = (() => {
  const THEMES = ['corkboard'];

  function getCurrent() {
    return localStorage.getItem('doubtnet-theme') || 'corkboard';
  }

  function apply(name) {
    document.documentElement.setAttribute('data-theme', name);
    localStorage.setItem('doubtnet-theme', name);
  }

  function init() {
    apply(getCurrent());
  }

  return { init, apply, getCurrent, THEMES };
})();
