/**
 * student.js
 * ----------
 * Student dashboard controller: phase display, doubt submission,
 * autosave, my doubts list, leaderboard preview.
 */

const Student = (() => {
  let myUsername = '';
  let countdownInterval = null;
  let autosaveTimer = null;

  const meLabel = document.getElementById('student-me-label');
  const logoutBtn = document.getElementById('student-logout-btn');
  const phaseBadge = document.getElementById('student-phase-badge');
  const countdownEl = document.getElementById('student-countdown');
  const phaseCard = document.getElementById('phase-status-card');
  const phaseIcon = document.getElementById('phase-icon');
  const phaseText = document.getElementById('phase-text');
  const doubtFormArea = document.getElementById('doubt-form-area');
  const doubtInput = document.getElementById('doubt-input');
  const charCounter = document.getElementById('char-counter');
  const autosaveIndicator = document.getElementById('autosave-indicator');
  const urgencyOptions = document.querySelectorAll('.urgency-option');
  const submitBtn = document.getElementById('submit-doubt-btn');
  const anonCounter = document.getElementById('anon-counter');
  const myDoubtsList = document.getElementById('my-doubts-list');
  const pointsBadge = document.getElementById('student-points-badge');
  const lbPreview = document.getElementById('leaderboard-preview');
  const studentLB = document.getElementById('student-leaderboard-body');

  let bound = false;

  const roomDisplay = document.getElementById('student-room-display');

  function start(username, state, roomCode, roomName) {
    myUsername = username;
    meLabel.textContent = `@${username}`;
    if (roomDisplay) {
      roomDisplay.textContent = `${roomName} [Code: ${roomCode}]`;
    }
    UI.showScreen('student-screen');

    updateState(state);
    requestMyDoubts();
    requestPoints();
    DoubtNetAPI.send({ type: 'get_draft' });

    bindEventsOnce();
    startCountdown(state);
    setupAutosave();
  }

  function bindEventsOnce() {
    if (bound) return;
    bound = true;

    logoutBtn.addEventListener('click', () => {
      DoubtNetAPI.disconnect();
      window.location.reload();
    });

    doubtInput.addEventListener('input', () => {
      const len = doubtInput.value.length;
      charCounter.textContent = `${len}/500`;
      submitBtn.disabled = len < 10;
    });

    urgencyOptions.forEach(opt => {
      opt.addEventListener('click', () => {
        urgencyOptions.forEach(o => o.classList.remove('active'));
        opt.classList.add('active');
        opt.querySelector('input').checked = true;
      });
    });

    submitBtn.addEventListener('click', submitDoubt);

    DoubtNetAPI.on('state_update', (data) => {
      updateState(data);
      startCountdown(data);
    });

    DoubtNetAPI.on('doubt_submitted', (data) => {
      if (data.status === 'flagged') {
        UI.toast('Doubt flagged for review — teacher will check it.', 'info', 4000);
      } else {
        UI.toast('Doubt submitted!', 'success');
      }
      doubtInput.value = '';
      charCounter.textContent = '0/500';
      submitBtn.disabled = true;
      requestMyDoubts();
    });

    DoubtNetAPI.on('doubt_count', (data) => {
      if (data.count !== undefined) {
        anonCounter.textContent = `${data.count} doubts submitted`;
      }
    });

    DoubtNetAPI.on('draft_saved', () => {
      autosaveIndicator.textContent = 'Saved';
      autosaveIndicator.classList.remove('saving');
    });

    DoubtNetAPI.on('draft', (data) => {
      if (data.text && !doubtInput.value) {
        doubtInput.value = data.text;
        const len = doubtInput.value.length;
        charCounter.textContent = `${len}/500`;
        submitBtn.disabled = len < 10;
      }
    });

    DoubtNetAPI.on('student_doubts', (data) => {
      renderMyDoubts(data.doubts || []);
    });

    DoubtNetAPI.on('leaderboard', (data) => {
      renderLeaderboard(data.entries || []);
    });

    DoubtNetAPI.on('points_finalized', () => {
      UI.toast('Points have been finalized! Check the leaderboard.', 'success', 5000);
      requestLeaderboard();
      requestPoints();
    });

    DoubtNetAPI.on('student_points', (data) => {
      if (data.data && data.data.total) {
        pointsBadge.textContent = `${data.data.total} pts`;
      }
    });
  }

  function updateState(state) {
    const phase = state.phase || 'no_class_today';
    const day = state.day || 0;
    const subject = state.subject || '';
    const secsRemaining = state.seconds_remaining || 0;

    const pinnedBanner = document.getElementById('student-pinned-banner');
    const pinnedText = document.getElementById('student-pinned-text');
    if (pinnedBanner && pinnedText) {
      if (state.pinned_doubt) {
        pinnedText.textContent = state.pinned_doubt.text;
        pinnedBanner.classList.remove('hidden');
      } else {
        pinnedBanner.classList.add('hidden');
      }
    }

    phaseBadge.textContent = phase.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

    phaseBadge.className = 'phase-badge';
    if (phase === 'doubt_window' || phase === 'grace_period') {
      phaseBadge.classList.add('urgent');
    } else if (phase === 'resolution_session') {
      phaseBadge.classList.add('resolved');
    }

    let icon = '';
    let text = '';

    switch (phase) {
      case 'before_class':
        icon = '&#9203;';
        text = subject ? `Waiting for ${subject} class...` : 'Waiting for class...';
        break;
      case 'class_active':
        icon = '&#128218;';
        text = `Class in session — ${state.minutes_remaining || '?'} min remaining`;
        break;
      case 'doubt_window':
        icon = '&#9888;&#65039;';
        if (state.allow_all_doubts || state.seconds_remaining === -1) {
          text = 'Doubt window OPEN! (Manual Mode — doubts allowed by teacher)';
        } else {
          text = `Doubt window OPEN! Submit your questions (${UI.formatCountdown(secsRemaining)} remaining)`;
        }
        break;
      case 'grace_period':
        icon = '&#9201;&#65039;';
        text = `Grace period — ${UI.formatCountdown(secsRemaining)} to submit`;
        break;
      case 'resolution_session':
        icon = '&#128269;&#65039;';
        text = 'Resolution day — teacher is answering doubts';
        break;
      case 'after_class':
        icon = '&#127881;';
        text = 'Class is over. See you next time!';
        break;
      default:
        icon = '&#128197;';
        text = 'No class scheduled today';
    }

    phaseIcon.innerHTML = icon;
    phaseText.textContent = text;

    const canSubmit = phase === 'doubt_window' || phase === 'grace_period';
    doubtFormArea.classList.toggle('disabled', !canSubmit);
    submitBtn.disabled = !canSubmit || doubtInput.value.length < 10;
    if (!canSubmit) {
      submitBtn.textContent = canSubmit ? 'Submit Doubt' : 'Awaiting doubt window...';
    } else {
      submitBtn.textContent = 'Submit Doubt';
    }
  }

  function startCountdown(state) {
    if (countdownInterval) {
      clearInterval(countdownInterval);
      countdownInterval = null;
    }

    const phase = state.phase || '';
    const secs = state.seconds_remaining || 0;

    if (phase === 'doubt_window' || phase === 'grace_period') {
      if (state.allow_all_doubts || secs === -1) {
        countdownEl.textContent = 'Manual Open';
        return;
      }
      let remaining = secs;
      countdownEl.textContent = UI.formatCountdown(remaining);
      countdownInterval = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
          countdownEl.textContent = '0:00';
          clearInterval(countdownInterval);
          countdownInterval = null;
        } else {
          countdownEl.textContent = UI.formatCountdown(remaining);
        }
      }, 1000);
    } else {
      countdownEl.textContent = '';
    }
  }

  function setupAutosave() {
    let lastText = '';
    setInterval(() => {
      const text = doubtInput.value;
      if (text && text !== lastText) {
        lastText = text;
        autosaveIndicator.textContent = 'Saving...';
        autosaveIndicator.classList.add('saving');
        DoubtNetAPI.send({ type: 'autosave_draft', text });
      }
    }, 3000);
  }

  function submitDoubt() {
    const text = doubtInput.value.trim();
    if (text.length < 10) {
      UI.toast('Doubt must be at least 10 characters.', 'error');
      return;
    }
    const urgencyEl = document.querySelector('.urgency-option.active input');
    const urgency = urgencyEl ? urgencyEl.value : 'clarification';
    DoubtNetAPI.send({ type: 'submit_doubt', text, urgency });
  }

  function requestMyDoubts() {
    DoubtNetAPI.send({ type: 'get_my_doubts' });
  }

  function requestPoints() {
    DoubtNetAPI.send({ type: 'get_my_points' });
  }

  function requestLeaderboard() {
    DoubtNetAPI.send({ type: 'get_leaderboard' });
  }

  function renderMyDoubts(doubts) {
    myDoubtsList.innerHTML = '';
    if (!doubts || doubts.length === 0) {
      myDoubtsList.innerHTML = '<p class="empty-state">No doubts submitted yet.</p>';
      return;
    }
    doubts.forEach(d => {
      const card = UI.el('div', 'doubt-card');
      const text = UI.el('div', 'doubt-text', d.text);
      const meta = UI.el('div', 'doubt-meta');

      const urgency = UI.el('span', `doubt-urgency ${d.urgency}`, d.urgency === 'blocking' ? 'Blocking' : 'Clarification');
      const day = UI.el('span', '', `Day ${d.day}`);
      const status = UI.el('span', `doubt-status ${d.status}`, d.status);

      meta.appendChild(urgency);
      meta.appendChild(day);
      meta.appendChild(status);
      card.appendChild(text);
      card.appendChild(meta);
      myDoubtsList.appendChild(card);
    });
  }

  function renderLeaderboard(entries) {
    if (!entries || entries.length === 0) return;
    lbPreview.classList.remove('hidden');
    studentLB.innerHTML = '';
    entries.slice(0, 10).forEach((e, i) => {
      const row = UI.el('div', 'lb-entry');
      row.style.animationDelay = `${i * 0.05}s`;
      const rank = UI.el('span', 'lb-rank', `#${e.rank}`);
      const name = e.real_name && e.show_real_name ? `${e.handle} (${e.real_name})` : e.handle;
      const handle = UI.el('span', 'lb-handle', name);
      const pts = UI.el('span', 'lb-points', `${e.total_points} pts`);
      row.appendChild(rank);
      row.appendChild(handle);
      row.appendChild(pts);
      studentLB.appendChild(row);
    });
  }

  return { start };
})();
