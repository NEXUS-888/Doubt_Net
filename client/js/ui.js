/**
 * ui.js
 * -----
 * Shared DOM helpers for DoubtNet.
 */

const UI = (() => {
  let previousScreen = null;

  function showScreen(id) {
    const active = document.querySelector('.screen:not(.hidden)');
    if (active && active.id !== 'leaderboard-screen') {
      previousScreen = active.id;
    }
    document.querySelectorAll('.screen').forEach(el => el.classList.add('hidden'));
    const screen = document.getElementById(id);
    if (screen) screen.classList.remove('hidden');
  }

  function getPreviousScreen() {
    return previousScreen;
  }

  function toast(message, type = 'info', duration = 3200) {
    const container = document.getElementById('toast-container');
    if (container && container.children.length >= 5) {
      container.children[0].remove();
    }
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    if (container) container.appendChild(el);
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

  function renderPodium(entries) {
    const podiumEl = document.getElementById('podium');
    const listEl = document.getElementById('lb-full-list');
    if (!podiumEl || !listEl) return;

    podiumEl.innerHTML = '';
    listEl.innerHTML = '';

    if (!entries || entries.length === 0) {
      podiumEl.innerHTML = '<p class="empty-state">No leaderboard scores computed yet.</p>';
      return;
    }

    const first = entries.find(e => e.rank === 1);
    const second = entries.find(e => e.rank === 2);
    const third = entries.find(e => e.rank === 3);

    const renderPlace = (e, className, numStr) => {
      if (!e) return '';
      const name = e.real_name && e.show_real_name ? `${e.handle} (${e.real_name})` : e.handle;
      const i = className === 'first' ? 2 : (className === 'second' ? 1 : 3);
      return `
        <div class="podium-place ${className}" style="animation-delay: calc(${i} * 150ms)">
          <div class="lb-note-handle" style="font-weight: bold; margin-bottom: 6px;">${escapeHtml(name)}</div>
          <div class="lb-note-points" style="font-weight: bold; font-family: var(--font-content); font-size: 14px; margin-bottom: 8px;">${e.total_points} pts</div>
          <div class="podium-block">
            <span class="podium-number">${numStr}</span>
          </div>
        </div>
      `;
    };

    let html = '';
    if (second) html += renderPlace(second, 'second', '2');
    if (first) html += renderPlace(first, 'first', '1');
    if (third) html += renderPlace(third, 'third', '3');
    podiumEl.innerHTML = html;

    entries.forEach(e => {
      const name = e.real_name && e.show_real_name ? `${e.handle} (${e.real_name})` : e.handle;
      const row = document.createElement('div');
      row.className = 'lb-entry';
      row.innerHTML = `
        <span class="lb-rank">#${e.rank}</span>
        <span class="lb-handle">${escapeHtml(name)}</span>
        <span class="lb-points">${e.total_points} pts</span>
      `;
      listEl.appendChild(row);
    });
  }

  const Modal = (() => {
    let onConfirm = null;
    let onCancel = null;

    function getElements() {
      return {
        el: document.getElementById('themed-modal'),
        titleEl: document.getElementById('themed-modal-title'),
        bodyEl: document.getElementById('themed-modal-body'),
        cancelBtn: document.getElementById('themed-modal-cancel'),
        confirmBtn: document.getElementById('themed-modal-confirm')
      };
    }

    function initEvents() {
      const { cancelBtn, confirmBtn, el, bodyEl } = getElements();
      if (cancelBtn && confirmBtn && el) {
        // Remove existing listeners to avoid duplicates
        const newCancelBtn = cancelBtn.cloneNode(true);
        const newConfirmBtn = confirmBtn.cloneNode(true);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

        newCancelBtn.addEventListener('click', () => {
          el.classList.add('hidden');
          if (onCancel) onCancel();
        });

        newConfirmBtn.addEventListener('click', () => {
          el.classList.add('hidden');
          if (onConfirm) {
            const input = bodyEl.querySelector('input, select');
            const checkboxes = bodyEl.querySelectorAll('input[type="checkbox"]:checked');
            if (checkboxes.length > 0) {
              const vals = Array.from(checkboxes).map(c => c.value);
              onConfirm(vals);
            } else if (input) {
              onConfirm(input.value);
            } else {
              onConfirm(true);
            }
          }
        });
      }
    }

    function showConfirm(title, message, confirmCb, cancelCb) {
      const { el, titleEl, bodyEl } = getElements();
      if (!el) return;
      titleEl.textContent = title;
      bodyEl.textContent = message;
      onConfirm = confirmCb;
      onCancel = cancelCb;
      initEvents();
      el.classList.remove('hidden');
    }

    function showPrompt(title, message, inputHtml, confirmCb, cancelCb) {
      const { el, titleEl, bodyEl } = getElements();
      if (!el) return;
      titleEl.textContent = title;
      bodyEl.innerHTML = `<p>${message}</p>${inputHtml}`;
      onConfirm = confirmCb;
      onCancel = cancelCb;
      initEvents();
      el.classList.remove('hidden');
    }

    return { showConfirm, showPrompt };
  })();

  function showSkeleton(containerId, count = 3) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = '';
    for (let i = 0; i < count; i++) {
      const card = document.createElement('div');
      card.className = 'pinned-note pending skeleton-card';
      card.style.opacity = '0.6';
      card.style.transform = `rotate(${(-1.5 + Math.random() * 3).toFixed(1)}deg)`;
      card.innerHTML = `
        <div class="pushpin"></div>
        <div style="background: rgba(58,47,31,0.15); height: 16px; margin-bottom: 8px; border-radius: 2px;"></div>
        <div style="background: rgba(58,47,31,0.15); height: 16px; margin-bottom: 12px; width: 80%; border-radius: 2px;"></div>
        <div style="background: rgba(58,47,31,0.1); height: 12px; width: 40%; border-radius: 2px;"></div>
      `;
      el.appendChild(card);
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

  return { showScreen, getPreviousScreen, renderPodium, toast, formatTime, formatDate, formatCountdown, escapeHtml, el, animateNumber, confetti, shake, Modal, showSkeleton };
})();
