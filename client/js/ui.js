/**
 * ui.js
 * -----
 * Shared DOM helpers for DoubtNet.
 */

const UI = (() => {
  function showScreen(id) {
    document.querySelectorAll('.screen').forEach(el => el.classList.add('hidden'));
    const screen = document.getElementById(id);
    if (screen) screen.classList.remove('hidden');
  }

  function toast(message, type = 'info', duration = 3200) {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
      el.classList.add('leaving');
      setTimeout(() => el.remove(), 250);
    }, duration);
  }

  function formatTime(ts) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function formatDate(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  }

  function formatCountdown(seconds) {
    if (seconds <= 0) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function animateNumber(element, from, to, duration = 600) {
    const start = performance.now();
    function frame(now) {
      const t = Math.min((now - start) / duration, 1);
      const current = Math.round(from + (to - from) * t);
      element.textContent = current;
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function confetti(container) {
    const colors = ['#8b5cf6', '#f59e0b', '#10b981', '#f43f5e', '#3b82f6', '#ec4899'];
    for (let i = 0; i < 80; i++) {
      const piece = document.createElement('div');
      const size = 4 + Math.random() * 6;
      const color = colors[Math.floor(Math.random() * colors.length)];
      const x = Math.random() * 100;
      const delay = Math.random() * 2;
      const duration = 1.5 + Math.random() * 2;
      piece.style.cssText = `
        position: fixed; top: -10px; left: ${x}%; width: ${size}px; height: ${size * 1.4}px;
        background: ${color}; border-radius: 2px; z-index: 200; pointer-events: none;
        animation: confetti-fall ${duration}s ease-in ${delay}s forwards;
        transform: rotate(${Math.random() * 360}deg);
      `;
      container.appendChild(piece);
      setTimeout(() => piece.remove(), (duration + delay) * 1000 + 100);
    }
  }

  function shake(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
      el.classList.remove('shake');
      void el.offsetWidth; // trigger reflow
      el.classList.add('shake');
      setTimeout(() => el.classList.remove('shake'), 400);
    }
  }

  return { showScreen, toast, formatTime, formatDate, formatCountdown, escapeHtml, el, animateNumber, confetti, shake };
})();
