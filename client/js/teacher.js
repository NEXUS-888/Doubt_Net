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
  let currentMode = 'class';
  let currentWebinarActive = false;

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

    // Request Notification permission when entering room dashboard
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    bindEventsOnce();
    requestSchedule();
    requestDoubts();
  }

  function bindEventsOnce() {
    if (bound) return;
    bound = true;

    logoutBtn.addEventListener('click', () => {
      App.signOut();
    });

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => {
          t.classList.remove('active');
          t.setAttribute('aria-selected', 'false');
        });
        tab.classList.add('active');
        tab.setAttribute('aria-selected', 'true');

        Object.keys(panels).forEach(key => {
          panels[key].classList.remove('active');
          panels[key].setAttribute('aria-hidden', 'true');
        });
        const panel = panels[tab.dataset.tab];
        if (panel) {
          panel.classList.add('active');
          panel.setAttribute('aria-hidden', 'false');
        }

        if (tab.dataset.tab === 'clusters') {
          UI.showSkeleton('cluster-list', 3);
          requestClusters();
        }
        if (tab.dataset.tab === 'live') {
          UI.showSkeleton('moderation-list', 2);
          UI.showSkeleton('live-approved-list', 3);
          requestDoubts();
        }
        if (tab.dataset.tab === 'resolution') {
          UI.showSkeleton('resolution-list', 3);
          requestResolution();
        }
        if (tab.dataset.tab === 'leaderboard') {
          UI.showSkeleton('teacher-leaderboard-body', 4);
          requestLeaderboard();
        }
      });
    });

    const toggleWeeklyBtn = document.getElementById('toggle-weekly-days-btn');
    const scheduleDaysEl = document.getElementById('schedule-days');
    if (toggleWeeklyBtn && scheduleDaysEl) {
      toggleWeeklyBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const isHidden = scheduleDaysEl.classList.toggle('hidden');
        toggleWeeklyBtn.textContent = isHidden ? 'Edit Weekly Days (5 Days) ▼' : 'Close Weekly Days (5 Days) ▲';
      });
    }

    const allowAllDoubtsBtn = document.getElementById('allow-all-doubts-btn');
    let allowAllDoubtsEnabled = false;

    // Mode Selector tabs listeners
    const modeClassBtn = document.getElementById('mode-class-btn');
    const modeWebinarBtn = document.getElementById('mode-webinar-btn');
    const classFields = document.getElementById('class-mode-fields');
    const webinarFields = document.getElementById('webinar-mode-fields');

    if (modeClassBtn && modeWebinarBtn) {
      modeClassBtn.addEventListener('click', () => {
        currentMode = 'class';
        modeClassBtn.classList.add('active');
        modeWebinarBtn.classList.remove('active');
        classFields.classList.remove('hidden');
        webinarFields.classList.add('hidden');
      });

      modeWebinarBtn.addEventListener('click', () => {
        currentMode = 'webinar';
        modeWebinarBtn.classList.add('active');
        modeClassBtn.classList.remove('active');
        webinarFields.classList.remove('hidden');
        classFields.classList.add('hidden');
      });
    }

    const toggleWebinarBtn = document.getElementById('toggle-webinar-btn');
    if (toggleWebinarBtn) {
      toggleWebinarBtn.addEventListener('click', () => {
        const nextActive = !currentWebinarActive;
        const subject = schedSubject.value.trim() || 'Webinar Session';

        DoubtNetAPI.send({
          type: 'set_schedule',
          schedule: {
            mode: 'webinar',
            webinar_active: nextActive,
            subject: subject
          }
        });

        UI.toast(nextActive ? 'Webinar session started!' : 'Webinar session stopped.', 'success');
      });
    }

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
      UI.Modal.showConfirm(
        'Finalize Clusters',
        'Finalize clusters? This will compute points and cannot be undone.',
        () => {
          DoubtNetAPI.send({ type: 'finalize_clusters' });
          UI.toast('Clusters finalized! Points computed.', 'success');
        }
      );
    });

    refreshLB.addEventListener('click', requestLeaderboard);
    revealLB.addEventListener('click', () => {
      DoubtNetAPI.send({ type: 'reveal_leaderboard' });
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

    DoubtNetAPI.on('presence', (data) => {
      const statsOnline = document.getElementById('stats-online-count');
      if (statsOnline && data.users) {
        statsOnline.textContent = data.users.length;
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

      // Update Session Stats Card
      const doubtsOnly = [...latestApprovedDoubts, ...flagged].filter(d => d.urgency !== 'feedback');
      const feedbackOnly = [...latestApprovedDoubts, ...flagged].filter(d => d.urgency === 'feedback');
      const resolved = latestApprovedDoubts.filter(d => d.status === 'resolved');

      const statsDoubts = document.getElementById('stats-doubts-count');
      const statsFeedback = document.getElementById('stats-feedback-count');
      const statsResolved = document.getElementById('stats-resolved-count');

      if (statsDoubts) statsDoubts.textContent = doubtsOnly.length;
      if (statsFeedback) statsFeedback.textContent = feedbackOnly.length;
      if (statsResolved) statsResolved.textContent = resolved.length;
    });

    DoubtNetAPI.on('clusters', (data) => {
      if (data.warning) {
        UI.toast(data.warning, 'info', 6000);
      }
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
    if (currentMode === 'webinar') {
      const schedule = {
        mode: 'webinar',
        webinar_active: currentWebinarActive,
        subject: schedSubject.value.trim() || 'Webinar Session',
      };
      DoubtNetAPI.send({ type: 'set_schedule', schedule });
      UI.toast('Webinar configuration saved!', 'success');
      return;
    }

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

    currentMode = schedule.mode || 'class';
    currentWebinarActive = schedule.webinar_active || false;

    // Update active mode tab trigger UI
    const modeClassBtn = document.getElementById('mode-class-btn');
    const modeWebinarBtn = document.getElementById('mode-webinar-btn');
    const classFields = document.getElementById('class-mode-fields');
    const webinarFields = document.getElementById('webinar-mode-fields');

    if (modeClassBtn && modeWebinarBtn) {
      if (currentMode === 'webinar') {
        modeWebinarBtn.classList.add('active');
        modeClassBtn.classList.remove('active');
        webinarFields.classList.remove('hidden');
        classFields.classList.add('hidden');
      } else {
        modeClassBtn.classList.add('active');
        modeWebinarBtn.classList.remove('active');
        classFields.classList.remove('hidden');
        webinarFields.classList.add('hidden');
      }
    }

    const toggleWebinarBtn = document.getElementById('toggle-webinar-btn');
    const webinarStatusText = document.getElementById('webinar-status-text');

    if (toggleWebinarBtn && webinarStatusText) {
      if (currentWebinarActive) {
        toggleWebinarBtn.textContent = 'Stop Webinar Session';
        toggleWebinarBtn.style.background = 'var(--pin-flagged)';
        toggleWebinarBtn.style.borderColor = 'var(--pin-flagged)';
        webinarStatusText.textContent = 'Session is currently open & accepting doubts/feedback.';
        webinarStatusText.style.color = 'var(--pin-approved)';
      } else {
        toggleWebinarBtn.textContent = 'Start Webinar Session';
        toggleWebinarBtn.style.background = 'var(--pin-approved)';
        toggleWebinarBtn.style.borderColor = 'var(--pin-approved)';
        webinarStatusText.textContent = 'Session is currently closed.';
        webinarStatusText.style.color = 'var(--paper-ink)';
      }
    }

    const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    for (let i = 1; i <= 5; i++) {
      const existing = (schedule.days || []).find(d => d.day === i);
      const row = document.createElement('div');
      row.className = 'schedule-day-row';
      row.dataset.day = i;
      row.innerHTML = `
        <label>${dayNames[i - 1]}</label>
        <input type="date" class="sched-date" value="${UI.escapeHtml(existing ? existing.date : '')}">
        <input type="time" class="sched-start" value="${UI.escapeHtml(existing ? existing.start : '09:00')}">
        <span style="color:var(--static-gray);font-size:11px">to</span>
        <input type="time" class="sched-end" value="${UI.escapeHtml(existing ? existing.end : '10:00')}">
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
      modList.innerHTML = '<p class="empty-state">No pending doubts to moderate.</p>';
      return;
    }
    flagged.forEach(d => {
      const item = document.createElement('div');
      item.className = 'pinned-note flagged';
      item.style.transform = `rotate(${(-5 + Math.random() * 10).toFixed(1)}deg)`;
      item.innerHTML = `
        <div class="pushpin"></div>
        <div class="note-content-text">${UI.escapeHtml(d.text)}</div>
        <div class="note-meta-row">
          <span class="note-author">@${UI.escapeHtml(d.username)} — Day ${d.day}</span>
        </div>
        <div class="note-meta-row" style="margin-top: 6px; border: none; padding: 0;">
          <span style="font-size:10px; color:var(--pin-flagged); font-weight: 600;">${UI.escapeHtml(d.moderation?.auto_flag || 'flagged')}</span>
        </div>
        <div class="note-action-tabs" style="display:flex; gap: 8px; margin-top: 12px; border-top: 1px dotted rgba(58,47,31,0.2); padding-top: 8px;">
          <button class="paper-tab mod-approve" style="font-size:11px; padding: 4px 8px; background: rgba(74, 124, 98, 0.1); border-color: rgba(74, 124, 98, 0.3); color: var(--pin-approved); flex: 1;" data-id="${d.id}">Approve</button>
          <button class="paper-tab mod-reject" style="font-size:11px; padding: 4px 8px; background: rgba(184, 68, 60, 0.1); border-color: rgba(184, 68, 60, 0.3); color: var(--pin-flagged); flex: 1;" data-id="${d.id}">Reject</button>
        </div>
      `;
      const approveBtn = item.querySelector('.mod-approve');
      const rejectBtn = item.querySelector('.mod-reject');

      const setPending = (pending) => {
        approveBtn.disabled = pending;
        rejectBtn.disabled = pending;
        if (pending) {
          approveBtn.textContent = '...';
          rejectBtn.textContent = '...';
        } else {
          approveBtn.textContent = 'Approve';
          rejectBtn.textContent = 'Reject';
        }
      };

      approveBtn.addEventListener('click', () => {
        setPending(true);
        const sent = DoubtNetAPI.send({ type: 'moderate_doubt', doubt_id: d.id, action: 'approve' });
        if (!sent) {
          setPending(false);
          UI.toast('Failed to send request. Offline.', 'error');
          return;
        }

        const onDone = (resp) => {
          if (String(resp.doubt_id) === String(d.id)) {
            DoubtNetAPI.off('moderation_done', onDone);
            clearTimeout(timeout);
            item.remove();
            UI.toast('Doubt approved', 'success');
          }
        };

        const timeout = setTimeout(() => {
          DoubtNetAPI.off('moderation_done', onDone);
          setPending(false);
          UI.toast('Request timed out. Please try again.', 'error');
        }, 10000);

        DoubtNetAPI.on('moderation_done', onDone);
      });

      rejectBtn.addEventListener('click', () => {
        setPending(true);
        const sent = DoubtNetAPI.send({ type: 'moderate_doubt', doubt_id: d.id, action: 'reject' });
        if (!sent) {
          setPending(false);
          UI.toast('Failed to send request. Offline.', 'error');
          return;
        }

        const onDone = (resp) => {
          if (String(resp.doubt_id) === String(d.id)) {
            DoubtNetAPI.off('moderation_done', onDone);
            clearTimeout(timeout);
            item.remove();
            UI.toast('Doubt rejected', 'info');
          }
        };

        const timeout = setTimeout(() => {
          DoubtNetAPI.off('moderation_done', onDone);
          setPending(false);
          UI.toast('Request timed out. Please try again.', 'error');
        }, 10000);

        DoubtNetAPI.on('moderation_done', onDone);
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



    [...approved].reverse().forEach(d => {
      const item = document.createElement('div');
      item.className = 'pinned-note approved';
      item.style.transform = `rotate(${(-1.5 + Math.random() * 3).toFixed(1)}deg)`;
      item.innerHTML = `
        <div class="pushpin"></div>
        <div class="note-content-text">${UI.escapeHtml(d.text)}</div>
        <div class="note-meta-row">
          <span class="note-author">@${UI.escapeHtml(d.username)} — Day ${d.day}</span>
          <span style="color:var(--pin-approved); font-weight:bold;">${UI.escapeHtml(d.urgency)}</span>
        </div>
        <div style="margin-top: 12px; border-top: 1px dotted rgba(58,47,31,0.2); padding-top: 8px; display: flex; justify-content: flex-end;">
          <button class="paper-tab pin-btn" style="font-size:11px; padding: 4px 8px; width: 100%;" data-id="${d.id}">Pin to Board</button>
        </div>
      `;
      item.querySelector('.pin-btn').addEventListener('click', () => {
        DoubtNetAPI.send({ type: 'pin_doubt', id: d.id });
        UI.toast('Doubt pinned to board!', 'success');
      });
      list.appendChild(item);
    });
  }

  function renderClusters(clusters) {
    clusterList.innerHTML = '';
    const keys = Object.keys(clusters);
    if (keys.length === 0) {
      clusterList.innerHTML = '<p class="empty-state">No doubt clusters computed yet.</p>';
      return;
    }
    keys.forEach((cid, idx) => {
      const c = clusters[cid];
      const card = document.createElement('div');
      card.className = 'pinned-note pending';
      card.style.transform = `rotate(${(-2.5 + Math.random() * 5).toFixed(1)}deg)`;
      card.innerHTML = `
        <div class="pushpin"></div>
        <div class="note-content-text">${UI.escapeHtml(c.representative_text || '(no text)')}</div>
        <div class="note-meta-row">
          <span class="note-author">Cluster ${UI.escapeHtml(cid)}</span>
          <span style="font-weight:bold; color:var(--pin-pending);">${c.size} doubts</span>
        </div>
        <div id="cluster-details-${cid}" class="hidden" style="margin-top: 8px; border-top: 1px dotted rgba(58,47,31,0.2); padding-top: 6px; font-size:10px; color:var(--chalk-muted); margin-bottom: 8px; word-break: break-all;">
          IDs: ${c.doubt_ids.join(', ')}
        </div>
        <div style="text-align: right; margin-bottom: 6px; width: 100%;">
          <button class="btn-ghost toggle-details-btn" data-target="cluster-details-${cid}" style="font-size: 8px; padding: 2px 6px;">Show IDs</button>
        </div>
        <div class="note-action-tabs" style="display:flex; gap: 8px; width: 100%;">
          <button class="paper-tab merge-btn" style="font-size:10px; padding: 4px 8px; flex: 1;">Merge...</button>
          <button class="paper-tab split-btn" style="font-size:10px; padding: 4px 8px; flex: 1;">Split</button>
        </div>
      `;
      card.querySelector('.toggle-details-btn').addEventListener('click', (e) => {
        const targetId = e.target.dataset.target;
        const detailsEl = card.querySelector(`#${targetId}`);
        if (detailsEl) {
          const isHidden = detailsEl.classList.toggle('hidden');
          e.target.textContent = isHidden ? 'Show IDs' : 'Hide IDs';
        }
      });
      card.querySelector('.merge-btn').addEventListener('click', () => {
        let optionsHtml = '<select id="merge-target-select">';
        Object.keys(latestClusters).forEach(otherId => {
          if (otherId !== cid) {
            const preview = latestClusters[otherId].representative_text || `Cluster ${otherId}`;
            optionsHtml += `<option value="${otherId}">Cluster ${otherId} ("${UI.escapeHtml(preview.substring(0, 40))}...")</option>`;
          }
        });
        optionsHtml += '</select>';

        if (Object.keys(latestClusters).length <= 1) {
          UI.toast('No other clusters to merge with.', 'error');
          return;
        }

        UI.Modal.showPrompt(
          'Merge Clusters',
          `Select a cluster to merge into Cluster ${cid}:`,
          optionsHtml,
          (targetId) => {
            if (targetId && targetId !== cid) {
              DoubtNetAPI.send({ type: 'merge_clusters', cluster_a: cid, cluster_b: targetId });
              UI.toast('Merging clusters...', 'info');
            }
          }
        );
      });
      card.querySelector('.split-btn').addEventListener('click', () => {
        let checkboxesHtml = '<div style="max-height: 200px; overflow-y: auto; text-align: left; margin-top: 12px;">';
        c.doubt_ids.forEach(did => {
          const doubtObj = latestApprovedDoubts.find(d => String(d.id) === String(did));
          const text = doubtObj ? doubtObj.text : `Doubt ${did}`;
          checkboxesHtml += `
            <label style="display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; cursor: pointer;">
              <input type="checkbox" value="${did}" style="width: auto; margin-top: 3px;">
              <span>"${UI.escapeHtml(text)}" <small style="color:var(--chalk-muted)">(ID: ${did})</small></span>
            </label>
          `;
        });
        checkboxesHtml += '</div>';

        if (c.doubt_ids.length <= 1) {
          UI.toast('Cannot split a cluster with 1 or fewer doubts.', 'error');
          return;
        }

        UI.Modal.showPrompt(
          'Split Cluster',
          `Select doubts to split out of Cluster ${cid}:`,
          checkboxesHtml,
          (selectedIds) => {
            if (selectedIds && selectedIds.length > 0) {
              if (selectedIds.length === c.doubt_ids.length) {
                UI.toast('Cannot split all doubts out of a cluster. Select at least one fewer.', 'error');
                return;
              }
              DoubtNetAPI.send({ type: 'split_cluster', cluster_id: cid, doubt_ids: selectedIds });
              UI.toast('Splitting cluster...', 'info');
            }
          }
        );
      });
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
      card.className = 'pinned-note pending';
      card.style.transform = `rotate(${(-2.5 + Math.random() * 5).toFixed(1)}deg)`;
      card.innerHTML = `
        <div class="pushpin"></div>
        <div class="note-content-text">${UI.escapeHtml(item.representative_text || '(no text)')}</div>
        <div class="note-meta-row">
          <span class="note-author">Cluster: ${UI.escapeHtml(item.cluster_id)}</span>
          <span style="font-weight:600;">Score: ${item.priority_score}</span>
        </div>
        <div class="note-meta-row" style="border:none; padding:0; margin-top:2px;">
          <span style="font-size:10px;">Freq: ${item.frequency} | Avg Urgency: ${item.avg_urgency_score}</span>
        </div>
        <div class="note-action-tabs" style="margin-top: 12px; border-top: 1px dotted rgba(58,47,31,0.2); padding-top: 8px; display:flex; gap:8px;">
          <button class="paper-tab resolve-btn" style="font-size:11px; padding: 4px 8px; flex:1; color:var(--pin-approved); background:rgba(74,124,98,0.1); border-color:rgba(74,124,98,0.3);">Resolve</button>
          <button class="paper-tab pin-btn" style="font-size:11px; padding: 4px 8px; flex:1; color:var(--pin-pending); background:rgba(201,154,74,0.1); border-color:rgba(201,154,74,0.3);">Pin</button>
        </div>
      `;
      card.querySelector('.resolve-btn').addEventListener('click', () => {
        UI.Modal.showConfirm(
          'Resolve Cluster',
          `Are you sure you want to resolve Cluster ${item.cluster_id}? This will archive all doubts in this cluster.`,
          () => {
            DoubtNetAPI.send({ type: 'resolve_doubt', cluster_id: item.cluster_id });
            UI.toast('Cluster resolved!', 'success');
          }
        );
      });
      card.querySelector('.pin-btn').addEventListener('click', () => {
        const firstDoubtId = item.doubt_ids && item.doubt_ids.length > 0 ? item.doubt_ids[0] : null;
        if (firstDoubtId) {
          DoubtNetAPI.send({ type: 'pin_doubt', id: firstDoubtId });
          UI.toast('Cluster pinned to board!', 'success');
        } else {
          UI.toast('No doubt IDs in cluster to pin.', 'error');
        }
      });
      resolutionList.appendChild(card);
    });
  }

  function renderTeacherLeaderboard(entries) {
    teacherLB.innerHTML = '';
    if (!entries || entries.length === 0) {
      teacherLB.innerHTML = '<p class="empty-state">No leaderboard data yet. Finalize clusters first.</p>';
      return;
    }
    entries.slice(0, 5).forEach((e, i) => {
      const card = UI.el('div', `lb-note rank-${e.rank}`);
      card.style.transform = `rotate(${(-2.5 + Math.random() * 5).toFixed(1)}deg)`;

      const pin = UI.el('div', 'pushpin');
      const rank = UI.el('div', 'lb-note-rank', `#${e.rank}`);
      const name = e.real_name && e.show_real_name ? `${e.handle} (${e.real_name})` : e.handle;
      const handle = UI.el('div', 'lb-note-handle', name);
      const pts = UI.el('div', 'lb-note-points', `${e.total_points} pts`);

      card.appendChild(pin);
      card.appendChild(rank);
      card.appendChild(handle);
      card.appendChild(pts);
      teacherLB.appendChild(card);
    });

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

    // Escape helper for the export document (prevents XSS in exported HTML)
    function esc(str) {
      if (str == null) return '';
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    let lbRows = '';
    latestLeaderboard.forEach(e => {
      const name = e.real_name && e.show_real_name ? `${esc(e.handle)} (${esc(e.real_name)})` : esc(e.handle);
      lbRows += `<tr><td>#${esc(e.rank)}</td><td>${name}</td><td>${esc(e.total_points)} pts</td></tr>`;
    });
    if (!lbRows) lbRows = '<tr><td colspan="3" style="text-align:center;">No leaderboard data available</td></tr>';

    let clusterCards = '';
    Object.keys(latestClusters).forEach(cid => {
      const c = latestClusters[cid];
      clusterCards += `
        <div style="border: 1px solid #ddd; padding: 12px; margin-bottom: 12px; border-radius: 6px;">
          <h4 style="margin: 0 0 6px; font-family: monospace;">Cluster: ${esc(cid)} (${esc(c.size)} doubts)</h4>
          <p style="margin: 0 0 8px; font-size: 14px; font-weight: bold;">"${esc(c.representative_text)}"</p>
          <span style="font-size: 11px; color: #666;">Doubt IDs: ${c.doubt_ids.map(id => esc(id)).join(', ')}</span>
        </div>
      `;
    });
    if (!clusterCards) clusterCards = '<p>No categorized clusters yet.</p>';

    let approvedDoubtsRows = '';
    latestApprovedDoubts.forEach(d => {
      approvedDoubtsRows += `<li><strong>@${esc(d.username)}</strong> (Day ${esc(d.day)}): "${esc(d.text)}"</li>`;
    });
    if (!approvedDoubtsRows) approvedDoubtsRows = '<li>No approved doubts in this session</li>';

    reportWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>DoubtNet Session Report</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Permanent+Marker&family=Special+Elite&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
          html, body {
            background-color: #17261f;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
            font-family: 'IBM Plex Sans', sans-serif;
          }
          
          .paper-sheet {
            background-color: #ead9b0;
            color: #3a2f1f;
            max-width: 800px;
            width: 90%;
            margin: 40px auto;
            padding: 40px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
            border-radius: 4px;
            position: relative;
            box-sizing: border-box;
            border: 1px solid rgba(58, 47, 31, 0.15);
          }
          
          .pushpin {
            width: 15px;
            height: 15px;
            background-color: #b8443c;
            border-radius: 50%;
            position: absolute;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
          }
          .pushpin::after {
            content: '';
            position: absolute;
            top: 5px;
            left: 5px;
            width: 5px;
            height: 5px;
            background-color: rgba(255, 255, 255, 0.5);
            border-radius: 50%;
          }

          h1 {
            font-family: 'Permanent Marker', cursive, sans-serif;
            margin-top: 10px;
            margin-bottom: 6px;
            font-size: 28px;
            color: #3a2f1f;
            border-bottom: 2px dashed rgba(58, 47, 31, 0.2);
            padding-bottom: 8px;
          }
          
          .meta {
            font-family: 'Special Elite', monospace, serif;
            font-size: 13px;
            opacity: 0.85;
            margin-bottom: 30px;
          }
          
          .section {
            margin-bottom: 32px;
          }
          
          h2 {
            font-family: 'Special Elite', monospace, serif;
            font-size: 18px;
            border-bottom: 1px dashed rgba(58, 47, 31, 0.2);
            padding-bottom: 6px;
            margin-bottom: 16px;
          }
          
          table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-family: 'IBM Plex Sans', sans-serif;
          }
          th, td {
            border: 1px dashed rgba(58, 47, 31, 0.25);
            padding: 10px 14px;
            text-align: left;
            font-size: 14px;
          }
          th {
            background-color: rgba(58, 47, 31, 0.05);
            font-weight: 600;
          }
          
          .cluster-card {
            border: 1px dashed rgba(58, 47, 31, 0.25);
            padding: 14px;
            margin-bottom: 14px;
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 0.1);
          }
          .cluster-card h4 {
            margin: 0 0 6px;
            font-family: 'Special Elite', monospace;
            font-size: 15px;
          }
          .cluster-card p {
            margin: 0 0 8px;
            font-size: 15px;
            font-style: italic;
          }
          .cluster-card span {
            font-size: 12px;
            opacity: 0.7;
          }
          
          .print-btn-container {
            display: flex;
            justify-content: flex-end;
            margin-bottom: 16px;
          }
          
          .print-btn {
            padding: 10px 20px;
            background-color: #3a2f1f;
            color: #ead9b0;
            border: 1px solid #3a2f1f;
            border-radius: 4px;
            font-family: 'IBM Plex Sans', sans-serif;
            font-weight: bold;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.15);
          }
          .print-btn:hover {
            background-color: #ead9b0;
            color: #3a2f1f;
          }

          @media print {
            html, body {
              background-color: white;
              color: black;
              display: block;
              min-height: auto;
            }
            .paper-sheet {
              background-color: white;
              color: black;
              box-shadow: none;
              border: none;
              padding: 0;
              margin: 0;
              width: 100%;
              max-width: 100%;
            }
            .pushpin {
              display: none;
            }
            .print-btn-container {
              display: none;
            }
            h1, h2 {
              color: black;
              border-bottom-color: black;
            }
            th, td, .cluster-card {
              border-color: black;
            }
            .cluster-card {
              background-color: transparent;
            }
          }
        </style>
      </head>
      <body>
        <div class="paper-sheet">
          <div class="pushpin"></div>
          <div class="print-btn-container">
            <button id="print-btn" class="print-btn">Print / Save as PDF</button>
          </div>
          <h1>DoubtNet Classroom Session Report</h1>
          <div class="meta">
            <strong>Room Scope:</strong> ${esc(roomText)} | <strong>Date Generated:</strong> ${esc(new Date().toLocaleString())}
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
            ${clusterCards.replace(/style="border: 1px solid #ddd; padding: 12px; margin-bottom: 12px; border-radius: 6px;"/g, 'class="cluster-card"')}
          </div>

          <div class="section">
            <h2>📝 Individual Approved Doubts</h2>
            <ul style="padding-left: 20px; font-size: 14px; font-family: 'IBM Plex Sans', sans-serif;">
              ${approvedDoubtsRows}
            </ul>
          </div>
        </div>
      </body>
      </html>
    `);
    reportWindow.document.close();

    // Bind event programmatically to bypass inline onclick CSP restrictions
    const printBtn = reportWindow.document.getElementById('print-btn');
    if (printBtn) {
      printBtn.addEventListener('click', () => {
        reportWindow.print();
      });
    }
  }

  return { start };
})();
