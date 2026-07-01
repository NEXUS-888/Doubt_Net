/**
 * teacher.js
 * ----------
 * Teacher dashboard controller: schedule, moderation, clusters,
 * resolution queue, and leaderboard management.
 */

const Teacher = (() => {
  let myUsername = '';
  let bound = false;
  let latestLeaderboard = [];
  let latestApprovedDoubts = [];
  let latestClusters = {};

  const meLabel = document.getElementById('teacher-me-label');
  const logoutBtn = document.getElementById('teacher-logout-btn');
  const tabs = document.querySelectorAll('.teacher-tab');
  const panels = {
    schedule: document.getElementById('panel-schedule'),
    live: document.getElementById('panel-live'),
    clusters: document.getElementById('panel-clusters'),
    resolution: document.getElementById('panel-resolution'),
    leaderboard: document.getElementById('panel-leaderboard'),
  };

  const schedWeekStart = document.getElementById('sched-week-start');
  const schedSubject = document.getElementById('sched-subject');
  const scheduleDays = document.getElementById('schedule-days');
  const saveScheduleBtn = document.getElementById('save-schedule-btn');
  const demoModeBtn = document.getElementById('demo-mode-btn');

  const modList = document.getElementById('moderation-list');
  const clusterList = document.getElementById('cluster-list');
  const autoClusterBtn = document.getElementById('auto-cluster-btn');
  const undoClusterBtn = document.getElementById('undo-cluster-btn');
  const finalizeBtn = document.getElementById('finalize-clusters-btn');
  const resolutionList = document.getElementById('resolution-list');
  const teacherLB = document.getElementById('teacher-leaderboard-body');
  const refreshLB = document.getElementById('refresh-leaderboard-btn');
  const revealLB = document.getElementById('reveal-leaderboard-btn');

  const roomDisplay = document.getElementById('teacher-room-display');

  function start(username, roomCode, roomName) {
    myUsername = username;
    meLabel.textContent = `@${username}`;
    if (roomDisplay) {
      roomDisplay.textContent = `${roomName} [Code: ${roomCode}]`;
    }
    UI.showScreen('teacher-screen');

    bindEventsOnce();
    requestSchedule();
    requestDoubts();
  }

  function bindEventsOnce() {
    if (bound) return;
    bound = true;

    logoutBtn.addEventListener('click', () => {
      DoubtNetAPI.disconnect();
      window.location.reload();
    });

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        Object.keys(panels).forEach(key => panels[key].classList.remove('active'));
        const panel = panels[tab.dataset.tab];
        if (panel) panel.classList.add('active');
        if (tab.dataset.tab === 'clusters') requestClusters();
        if (tab.dataset.tab === 'live') requestDoubts();
        if (tab.dataset.tab === 'resolution') requestResolution();
        if (tab.dataset.tab === 'leaderboard') requestLeaderboard();
      });
    });

    const allowAllDoubtsBtn = document.getElementById('allow-all-doubts-btn');
    let allowAllDoubtsEnabled = false;

    saveScheduleBtn.addEventListener('click', saveSchedule);
    demoModeBtn.addEventListener('click', toggleDemo);
    
    allowAllDoubtsBtn.addEventListener('click', () => {
      allowAllDoubtsEnabled = !allowAllDoubtsEnabled;
      DoubtNetAPI.send({ type: 'toggle_allow_all_doubts', enabled: allowAllDoubtsEnabled });
      updateAllowAllDoubtsUI(allowAllDoubtsEnabled);
    });

    autoClusterBtn.addEventListener('click', () => {
      DoubtNetAPI.send({ type: 'auto_cluster' });
      UI.toast('Clustering in progress...', 'info');
    });

    undoClusterBtn.addEventListener('click', () => {
      DoubtNetAPI.send({ type: 'undo_cluster' });
    });

    finalizeBtn.addEventListener('click', () => {
      if (confirm('Finalize clusters? This will compute points and cannot be undone.')) {
        DoubtNetAPI.send({ type: 'finalize_clusters' });
        UI.toast('Clusters finalized! Points computed.', 'success');
      }
    });

    refreshLB.addEventListener('click', requestLeaderboard);
    revealLB.addEventListener('click', () => {
      DoubtNetAPI.send({ type: 'get_leaderboard' });
    });

    const unpinBtn = document.getElementById('teacher-unpin-btn');
    if (unpinBtn) {
      unpinBtn.addEventListener('click', () => {
        DoubtNetAPI.send({ type: 'pin_doubt', id: null });
      });
    }

    const exportBtn = document.getElementById('export-report-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', exportSessionReport);
    }

    DoubtNetAPI.on('schedule_info', (data) => {
      const schedule = data.schedule || {};
      allowAllDoubtsEnabled = schedule.allow_all_doubts || false;
      populateScheduleForm(schedule);
    });

    DoubtNetAPI.on('state_update', (data) => {
      if (data.allow_all_doubts !== undefined) {
        allowAllDoubtsEnabled = data.allow_all_doubts;
        updateAllowAllDoubtsUI(allowAllDoubtsEnabled);
      }
      const pinnedBanner = document.getElementById('teacher-pinned-banner');
      const pinnedText = document.getElementById('teacher-pinned-text');
      if (pinnedBanner && pinnedText) {
        if (data.pinned_doubt) {
          pinnedText.textContent = data.pinned_doubt.text;
          pinnedBanner.classList.remove('hidden');
        } else {
          pinnedBanner.classList.add('hidden');
        }
      }
    });

    let lastFlaggedCount = 0;
    DoubtNetAPI.on('all_doubts', (data) => {
      const flagged = data.flagged || [];
      latestApprovedDoubts = data.approved || [];
      if (flagged.length > lastFlaggedCount) {
        playChime();
        triggerNotification('DoubtNet Alert', `New doubts pending review (${flagged.length})`);
      }
      lastFlaggedCount = flagged.length;
      renderModeration(flagged);
      renderApproved(latestApprovedDoubts);
    });

    DoubtNetAPI.on('clusters', (data) => {
      latestClusters = data.clusters || {};
      renderClusters(latestClusters);
    });

    DoubtNetAPI.on('cluster_updated', (data) => {
      latestClusters = data.clusters || {};
      renderClusters(latestClusters);
    });

    DoubtNetAPI.on('resolution_queue', (data) => {
      renderResolution(data.clusters || []);
    });

    DoubtNetAPI.on('leaderboard', (data) => {
      latestLeaderboard = data.entries || [];
      renderTeacherLeaderboard(latestLeaderboard);
    });
  }

  function requestSchedule() {
    DoubtNetAPI.send({ type: 'get_schedule' });
  }

  function requestDoubts() {
    DoubtNetAPI.send({ type: 'get_doubts' });
  }

  function requestClusters() {
    DoubtNetAPI.send({ type: 'get_clusters' });
  }

  function requestResolution() {
    DoubtNetAPI.send({ type: 'get_resolution_queue' });
  }

  function requestLeaderboard() {
    DoubtNetAPI.send({ type: 'get_leaderboard' });
  }

  function saveSchedule() {
    const days = [];
    document.querySelectorAll('.schedule-day-row').forEach(row => {
      const dayNum = parseInt(row.dataset.day);
      const date = row.querySelector('.sched-date').value;
      const start = row.querySelector('.sched-start').value;
      const end = row.querySelector('.sched-end').value;
      const type = dayNum === 5 ? 'resolution' : 'class';
      if (date && start && end) {
        days.push({ day: dayNum, date, start, end, type });
      }
    });

    const schedule = {
      week_start: schedWeekStart.value,
      subject: schedSubject.value,
      days,
      doubt_window_minutes: 5,
      grace_period_seconds: 90,
    };

    DoubtNetAPI.send({ type: 'set_schedule', schedule });
    UI.toast('Schedule saved!', 'success');
  }

  function toggleDemo() {
    DoubtNetAPI.send({ type: 'start_demo_mode' });
    UI.toast('Demo mode enabled — doubt window always open.', 'info', 4000);
  }

  function populateScheduleForm(schedule) {
    schedWeekStart.value = schedule.week_start || '';
    schedSubject.value = schedule.subject || '';
    scheduleDays.innerHTML = '';

    const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    for (let i = 1; i <= 5; i++) {
      const existing = (schedule.days || []).find(d => d.day === i);
      const row = document.createElement('div');
      row.className = 'schedule-day-row';
      row.dataset.day = i;
      row.innerHTML = `
        <label>${dayNames[i - 1]}</label>
        <input type="date" class="sched-date" value="${existing ? existing.date : ''}">
        <input type="time" class="sched-start" value="${existing ? existing.start : '09:00'}">
        <span style="color:var(--static-gray);font-size:11px">to</span>
        <input type="time" class="sched-end" value="${existing ? existing.end : '10:00'}">
        ${i === 5 ? '<span style="font-size:10px;color:var(--dn-amber)">Resolution day</span>' : ''}
      `;
      scheduleDays.appendChild(row);
    }

    updateAllowAllDoubtsUI(schedule.allow_all_doubts || false);
  }

  function updateAllowAllDoubtsUI(enabled) {
    const btn = document.getElementById('allow-all-doubts-btn');
    if (!btn) return;
    if (enabled) {
      btn.textContent = 'Allow All Doubts: ON';
      btn.style.borderColor = 'var(--success-green)';
      btn.style.color = 'var(--success-green)';
    } else {
      btn.textContent = 'Allow All Doubts: OFF';
      btn.style.borderColor = 'var(--dn-amber)';
      btn.style.color = 'var(--dn-amber)';
    }
  }

  function renderModeration(flagged) {
    modList.innerHTML = '';
    if (!flagged || flagged.length === 0) {
      modList.innerHTML = '<p class="empty-state">No flagged doubts.</p>';
      return;
    }
    flagged.forEach(d => {
      const item = document.createElement('div');
      item.className = 'moderation-item';
      item.innerHTML = `
        <div class="mod-text">
          ${UI.escapeHtml(d.text)}
          <div class="mod-meta">@${UI.escapeHtml(d.username)} — Day ${d.day} — ${UI.escapeHtml(d.moderation?.auto_flag || 'flagged')}</div>
          <div class="mod-flag">${UI.escapeHtml(d.moderation?.auto_flag || 'unknown')}</div>
        </div>
        <div class="mod-actions">
          <button class="btn-ghost mod-approve" data-id="${d.id}" style="border-color:var(--success-green);color:var(--success-green)">Approve</button>
          <button class="btn-ghost mod-reject" data-id="${d.id}" style="border-color:var(--error-red);color:var(--error-red)">Reject</button>
        </div>
      `;
      item.querySelector('.mod-approve').addEventListener('click', () => {
        DoubtNetAPI.send({ type: 'moderate_doubt', doubt_id: d.id, action: 'approve' });
        item.remove();
        UI.toast('Doubt approved', 'success');
      });
      item.querySelector('.mod-reject').addEventListener('click', () => {
        DoubtNetAPI.send({ type: 'moderate_doubt', doubt_id: d.id, action: 'reject' });
        item.remove();
        UI.toast('Doubt rejected', 'info');
      });
      modList.appendChild(item);
    });
  }

  function renderApproved(approved) {
    const list = document.getElementById('live-approved-list');
    list.innerHTML = '';
    if (!approved || approved.length === 0) {
      list.innerHTML = '<p class="empty-state">No approved doubts yet.</p>';
      return;
    }
    // Reverse to show newest first
    [...approved].reverse().forEach(d => {
      const item = document.createElement('div');
      item.className = 'moderation-item'; 
      
      const modText = document.createElement('div');
      modText.className = 'mod-text';
      modText.innerHTML = `
        ${UI.escapeHtml(d.text)}
        <div class="mod-meta">@${UI.escapeHtml(d.username)} — Day ${d.day} — Priority: ${UI.escapeHtml(d.urgency)}</div>
        <div class="mod-flag" style="background:var(--dn-emerald-dim);color:var(--dn-emerald);display:inline-block;">Approved</div>
      `;
      
      const actions = document.createElement('div');
      actions.className = 'mod-actions';
      
      const pinBtn = document.createElement('button');
      pinBtn.className = 'btn-ghost';
      pinBtn.textContent = 'Pin to Board';
      pinBtn.style.cssText = 'border-color:var(--dn-amber);color:var(--dn-amber);font-size:11px;padding:4px 8px;';
      pinBtn.addEventListener('click', () => {
        DoubtNetAPI.send({ type: 'pin_doubt', id: d.id });
        UI.toast('Doubt pinned to board!', 'success');
      });
      
      actions.appendChild(pinBtn);
      item.appendChild(modText);
      item.appendChild(actions);
      list.appendChild(item);
    });
  }

  function renderClusters(clusters) {
    clusterList.innerHTML = '';
    const keys = Object.keys(clusters);
    if (keys.length === 0) {
      clusterList.innerHTML = '<p class="empty-state">No clusters yet. Run auto-cluster after approving doubts.</p>';
      return;
    }
    keys.forEach((cid, idx) => {
      const c = clusters[cid];
      const card = document.createElement('div');
      card.className = 'cluster-card';
      card.style.animationDelay = `${idx * 0.05}s`;

      const header = document.createElement('div');
      header.className = 'cluster-header';
      header.innerHTML = `
        <span class="cluster-id">${cid}</span>
        <span class="cluster-size">${c.size} doubt${c.size !== 1 ? 's' : ''}</span>
      `;

      const rep = document.createElement('div');
      rep.className = 'cluster-rep';
      rep.textContent = c.representative_text || '(no text)';

      const actions = document.createElement('div');
      actions.className = 'cluster-actions-row';

      const mergeBtn = document.createElement('button');
      mergeBtn.className = 'btn-ghost';
      mergeBtn.textContent = 'Merge into...';
      mergeBtn.style.cssText = 'font-size:10px;padding:4px 8px';
      mergeBtn.addEventListener('click', () => {
        const target = prompt('Enter cluster ID to merge into this one:');
        if (target && target !== cid) {
          DoubtNetAPI.send({ type: 'merge_clusters', cluster_a: cid, cluster_b: target });
        }
      });

      const splitBtn = document.createElement('button');
      splitBtn.className = 'btn-ghost';
      splitBtn.textContent = 'Split';
      splitBtn.style.cssText = 'font-size:10px;padding:4px 8px';
      splitBtn.addEventListener('click', () => {
        const ids = prompt('Enter doubt IDs to extract (comma-separated):');
        if (ids) {
          const doubtIds = ids.split(',').map(s => s.trim()).filter(Boolean);
          DoubtNetAPI.send({ type: 'split_cluster', cluster_id: cid, doubt_ids: doubtIds });
        }
      });

      actions.appendChild(mergeBtn);
      actions.appendChild(splitBtn);

      const doubtsEl = document.createElement('div');
      doubtsEl.className = 'cluster-doubts';
      doubtsEl.textContent = `IDs: ${c.doubt_ids.join(', ')}`;
      doubtsEl.style.cssText = 'font-size:10px;color:var(--static-gray);margin-top:6px';

      card.appendChild(header);
      card.appendChild(rep);
      card.appendChild(actions);
      card.appendChild(doubtsEl);
      clusterList.appendChild(card);
    });
  }

  function renderResolution(queue) {
    resolutionList.innerHTML = '';
    if (!queue || queue.length === 0) {
      resolutionList.innerHTML = '<p class="empty-state">No unresolved clusters.</p>';
      return;
    }
    queue.forEach((item, idx) => {
      const card = document.createElement('div');
      card.className = 'resolution-item';
      card.style.animationDelay = `${idx * 0.05}s`;

      const priority = document.createElement('div');
      priority.className = 'res-priority';
      priority.textContent = `Priority: ${item.priority_score} | Freq: ${item.frequency} | Urgency: ${item.avg_urgency_score}`;

      const text = document.createElement('div');
      text.className = 'res-text';
      text.textContent = item.representative_text || '(no text)';

      const stats = document.createElement('div');
      stats.className = 'res-stats';
      stats.textContent = `Cluster: ${item.cluster_id}`;

      const resolveBtn = document.createElement('button');
      resolveBtn.className = 'btn-ghost';
      resolveBtn.textContent = 'Mark Resolved';
      resolveBtn.style.cssText = 'border-color:var(--dn-emerald);color:var(--dn-emerald);margin-top:8px;';
      resolveBtn.addEventListener('click', () => {
        DoubtNetAPI.send({ type: 'resolve_doubt', cluster_id: item.cluster_id });
        card.remove();
        UI.toast('Cluster resolved!', 'success');
      });

      const pinBtn = document.createElement('button');
      pinBtn.className = 'btn-ghost';
      pinBtn.textContent = 'Pin to Board';
      pinBtn.style.cssText = 'border-color:var(--dn-amber);color:var(--dn-amber);margin-top:8px;margin-left:8px;';
      pinBtn.addEventListener('click', () => {
        const firstDoubtId = item.doubt_ids && item.doubt_ids.length > 0 ? item.doubt_ids[0] : null;
        if (firstDoubtId) {
          DoubtNetAPI.send({ type: 'pin_doubt', id: firstDoubtId });
          UI.toast('Cluster pinned to board!', 'success');
        } else {
          UI.toast('No doubt IDs in cluster to pin.', 'error');
        }
      });

      card.appendChild(priority);
      card.appendChild(text);
      card.appendChild(stats);
      card.appendChild(resolveBtn);
      card.appendChild(pinBtn);
      resolutionList.appendChild(card);
    });
  }

  function renderTeacherLeaderboard(entries) {
    teacherLB.innerHTML = '';
    if (!entries || entries.length === 0) {
      teacherLB.innerHTML = '<p class="empty-state">No leaderboard data yet. Finalize clusters first.</p>';
      return;
    }
    const table = document.createElement('div');
    entries.forEach((e, i) => {
      const row = UI.el('div', 'lb-entry');
      row.style.animationDelay = `${i * 0.03}s`;
      const rank = UI.el('span', 'lb-rank', `#${e.rank}`);
      const name = e.real_name && e.show_real_name ? `${e.handle} (${e.real_name})` : e.handle;
      const handle = UI.el('span', 'lb-handle', name);
      const pts = UI.el('span', 'lb-points', `${e.total_points} pts`);
      row.appendChild(rank);
      row.appendChild(handle);
      row.appendChild(pts);
      table.appendChild(row);
    });
    teacherLB.appendChild(table);

    // Also show to students if we're revealing
    if (entries.length > 0) {
      UI.confetti(document.getElementById('confetti-canvas') || document.body);
    }
  }

  function playChime() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(659.25, audioCtx.currentTime); // E5
      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
      osc.start(audioCtx.currentTime);
      osc.stop(audioCtx.currentTime + 0.35);
      
      setTimeout(() => {
        const osc2 = audioCtx.createOscillator();
        const gain2 = audioCtx.createGain();
        osc2.connect(gain2);
        gain2.connect(audioCtx.destination);
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880.00, audioCtx.currentTime); // A5
        gain2.gain.setValueAtTime(0.12, audioCtx.currentTime);
        gain2.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.5);
        osc2.start(audioCtx.currentTime);
        osc2.stop(audioCtx.currentTime + 0.5);
      }, 150);
    } catch (e) {
      console.warn('Audio Context block', e);
    }
  }

  function triggerNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(title, { body });
    }
  }

  function exportSessionReport() {
    const reportWindow = window.open('', '_blank');
    if (!reportWindow) {
      UI.toast('Popups are blocked! Please enable popups to export report.', 'error');
      return;
    }

    const roomText = roomDisplay ? roomDisplay.textContent : 'Classroom';
    
    let lbRows = '';
    latestLeaderboard.forEach(e => {
      const name = e.real_name && e.show_real_name ? `${e.handle} (${e.real_name})` : e.handle;
      lbRows += `<tr><td>#${e.rank}</td><td>${name}</td><td>${e.total_points} pts</td></tr>`;
    });
    if (!lbRows) lbRows = '<tr><td colspan="3" style="text-align:center;">No leaderboard data available</td></tr>';

    let clusterCards = '';
    Object.keys(latestClusters).forEach(cid => {
      const c = latestClusters[cid];
      clusterCards += `
        <div style="border: 1px solid #ddd; padding: 12px; margin-bottom: 12px; border-radius: 6px;">
          <h4 style="margin: 0 0 6px; font-family: monospace;">Cluster: ${cid} (${c.size} doubts)</h4>
          <p style="margin: 0 0 8px; font-size: 14px; font-weight: bold;">"${c.representative_text}"</p>
          <span style="font-size: 11px; color: #666;">Doubt IDs: ${c.doubt_ids.join(', ')}</span>
        </div>
      `;
    });
    if (!clusterCards) clusterCards = '<p>No categorized clusters yet.</p>';

    let approvedDoubtsRows = '';
    latestApprovedDoubts.forEach(d => {
      approvedDoubtsRows += `<li><strong>@${d.username}</strong> (Day ${d.day}): "${d.text}"</li>`;
    });
    if (!approvedDoubtsRows) approvedDoubtsRows = '<li>No approved doubts in this session</li>';

    reportWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>DoubtNet Session Report</title>
        <style>
          body { font-family: 'Inter', sans-serif; padding: 30px; color: #111; line-height: 1.5; }
          h1 { margin-bottom: 4px; font-size: 24px; }
          .meta { font-size: 13px; color: #555; margin-bottom: 30px; border-bottom: 2px solid #333; padding-bottom: 10px; }
          .section { margin-bottom: 30px; }
          h2 { font-size: 18px; border-bottom: 1px solid #ddd; padding-bottom: 6px; margin-bottom: 15px; }
          table { width: 100%; border-collapse: collapse; margin-top: 10px; }
          th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; font-size: 13px; }
          th { background-color: #f5f5f5; }
          @media print {
            body { padding: 0; }
            button { display: none; }
          }
        </style>
      </head>
      <body>
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h1>DoubtNet Classroom Session Report</h1>
          <button onclick="window.print()" style="padding: 8px 16px; background-color: #7c3aed; color: white; border: none; border-radius: 4px; cursor: pointer;">Print / Save as PDF</button>
        </div>
        <div class="meta">
          <strong>Room Scope:</strong> ${roomText} | <strong>Date Generated:</strong> ${new Date().toLocaleString()}
        </div>
        
        <div class="section">
          <h2>🏆 Student Leaderboard</h2>
          <table>
            <thead>
              <tr><th>Rank</th><th>Student handle</th><th>Points</th></tr>
            </thead>
            <tbody>
              ${lbRows}
            </tbody>
          </table>
        </div>

        <div class="section">
          <h2>🧠 Categorized Doubt Clusters (Machine Learning Groups)</h2>
          ${clusterCards}
        </div>

        <div class="section">
          <h2>📝 Individual Approved Doubts</h2>
          <ul style="padding-left: 20px; font-size: 13px;">
            ${approvedDoubtsRows}
          </ul>
        </div>
      </body>
      </html>
    `);
    reportWindow.document.close();
  }

  // Request Notification permission when mounting
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }

  return { start };
})();
