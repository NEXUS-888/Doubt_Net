/**
 * app.js
 * ------
 * Entrypoint for DoubtNet. Manages room picker rendering and routes
 * authenticated users to student or teacher dashboard based on role.
 */

const App = (() => {
  let _username = null;
  let _role = null;
  let _session = null;
  let reconnectAttempts = 0;

  function setSession(username, password, role) {
    _session = { username, password, role };
  }

  function setRoomSession(roomCode, roomName) {
    if (_session) {
      _session.roomCode = roomCode;
      _session.roomName = roomName;
    }
  }

  function clearSession() {
    _session = null;
  }

  function generateRandomCode() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let code = '';
    for (let i = 0; i < 6; i++) {
      code += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return code;
  }

  function showRoomPicker(username, role, rooms) {
    _username = username;
    _role = role;

    // Set user label
    const meLabel = document.getElementById('picker-me-label');
    meLabel.textContent = username + ' (' + role + ')';

    // Show/hide create vs join areas
    const createArea = document.getElementById('picker-create-area');
    const joinArea = document.getElementById('picker-join-area');
    const subtitle = document.getElementById('picker-subtitle');

    if (role === 'teacher') {
      createArea.classList.remove('hidden');
      joinArea.classList.add('hidden');
      subtitle.textContent = rooms.length
        ? 'Select a room to manage, or create a new one.'
        : 'Create your first room to get started.';
    } else {
      createArea.classList.add('hidden');
      joinArea.classList.remove('hidden');
      subtitle.textContent = rooms.length
        ? 'Select a room to enter, or join a new one with a code.'
        : 'Join your first room with a code from your teacher.';
    }

    // Render room cards
    renderRoomCards(rooms, role);

    // Show picker screen
    UI.showScreen('room-picker-screen');
  }

  function renderRoomCards(rooms, role) {
    const grid = document.getElementById('rooms-grid');
    grid.innerHTML = '';

    if (rooms.length === 0) {
      grid.innerHTML = '<p class="empty-state">No rooms yet — ' +
        (role === 'teacher' ? 'create one below.' : 'join one below.') + '</p>';
      return;
    }

    rooms.forEach((room, i) => {
      const rotations = [-2.5, 1.8, -1.2, 2.1, -0.8, 1.5];
      const rot = rotations[i % rotations.length];
      const pinClass = role === 'teacher' ? 'approved' : 'pending';

      const card = document.createElement('div');
      card.className = 'pinned-note room-card ' + pinClass;
      card.style.transform = 'rotate(' + rot + 'deg)';
      card.setAttribute('data-room-code', room.code);
      card.innerHTML =
        '<div class="pushpin"></div>' +
        '<div class="room-card-name">' + escapeHtml(room.name) + '</div>' +
        '<div class="room-card-code">' + escapeHtml(room.code) + '</div>' +
        '<div class="room-card-meta">' +
          (role === 'teacher'
            ? room.student_count + ' student' + (room.student_count !== 1 ? 's' : '')
            : 'Teacher: ' + escapeHtml(room.teacher)) +
        '</div>';

      card.addEventListener('click', () => selectRoom(room.code));
      grid.appendChild(card);
    });
  }

  function selectRoom(roomCode) {
    const pickerError = document.getElementById('picker-error');
    pickerError.textContent = 'Entering room...';

    // Listen for room_entered
    DoubtNetAPI.off('room_entered');
    DoubtNetAPI.on('room_entered', (data) => {
      DoubtNetAPI.off('room_entered');
      pickerError.textContent = '';
      onAuthenticated(data.username, data.role, data.state, data.room_code, data.room_name, data.protocol_version);
    });

    DoubtNetAPI.send({ type: 'select_room', room_code: roomCode });
  }

  function onAuthenticated(username, role, state, roomCode, roomName, protocolVersion) {
    if (protocolVersion && protocolVersion !== 'v1.2') {
      console.warn('Protocol version mismatch! Client: v1.2, Server: ' + protocolVersion);
    }
    // Leave auth-phase listeners behind once the user has entered a room.
    DoubtNetAPI.off('rooms_list');
    DoubtNetAPI.off('auth_error');

    // Store room session details
    setRoomSession(roomCode, roomName);

    // Mark connection as in-room so auto-reconnect is active for unexpected drops
    DoubtNetAPI.setInRoom(true);

    if (role === 'teacher') {
      Teacher.start(username, roomCode, roomName);
    } else {
      Student.start(username, state, roomCode, roomName);
    }
  }

  function bindPickerEvents() {
    // Logout from picker
    const logoutBtn = document.getElementById('picker-logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        DoubtNetAPI.disconnect();
        clearSession();
        _username = null;
        _role = null;
        UI.showScreen('landing-screen');
      });
    }

    // Teacher: Create Room form
    const createForm = document.getElementById('picker-create-form');
    if (createForm) {
      createForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const nameInput = document.getElementById('picker-create-name');
        const roomName = nameInput.value.trim();
        const pickerError = document.getElementById('picker-error');
        if (pickerError) pickerError.textContent = '';

        if (!roomName) return;
        if (roomName.length < 3 || roomName.length > 50) {
          if (pickerError) pickerError.textContent = 'Room name must be 3-50 characters.';
          UI.shake('room-picker-screen');
          return;
        }
        if (!/^[a-zA-Z0-9\s\-_]+$/.test(roomName)) {
          if (pickerError) pickerError.textContent = 'Room name can only contain letters, numbers, spaces, - and _.';
          UI.shake('room-picker-screen');
          return;
        }

        const roomCode = generateRandomCode();

        // Listen for auto-enter after creation
        DoubtNetAPI.off('room_entered');
        DoubtNetAPI.on('room_entered', (data) => {
          DoubtNetAPI.off('room_entered');
          nameInput.value = '';
          onAuthenticated(data.username, data.role, data.state, data.room_code, data.room_name, data.protocol_version);
        });

        DoubtNetAPI.send({ type: 'create_room', room_name: roomName, room_code: roomCode });
      });
    }

    // Student: Join Room form
    const joinForm = document.getElementById('picker-join-form');
    if (joinForm) {
      joinForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const codeInput = document.getElementById('picker-join-code');
        const roomCode = codeInput.value.trim().toUpperCase();
        const pickerError = document.getElementById('picker-error');
        if (pickerError) pickerError.textContent = '';

        if (!roomCode) return;
        if (roomCode.length !== 6 || !/^[A-Z0-9]+$/.test(roomCode)) {
          if (pickerError) pickerError.textContent = 'Room code must be 6 alphanumeric characters.';
          UI.shake('room-picker-screen');
          return;
        }

        // Listen for auto-enter after joining
        DoubtNetAPI.off('room_entered');
        DoubtNetAPI.on('room_entered', (data) => {
          DoubtNetAPI.off('room_entered');
          codeInput.value = '';
          onAuthenticated(data.username, data.role, data.state, data.room_code, data.room_name, data.protocol_version);
        });

        DoubtNetAPI.send({ type: 'join_room', room_code: roomCode });
      });
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function init() {
    Theme.init();
    Auth.init();
    bindPickerEvents();

    // Listen for WebSocket open/close for reconnect banner & Session Resume
    DoubtNetAPI.on('close', () => {
      const banner = document.getElementById('connection-status-banner');
      if (!banner || !DoubtNetAPI.isInRoom()) return;

      reconnectAttempts++;
      if (reconnectAttempts > 5) {
        banner.textContent = "Disconnected — please check your internet connection or refresh.";
        banner.className = "connection-status-banner disconnected";
        banner.classList.remove('hidden');
      } else {
        banner.textContent = "Reconnecting...";
        banner.className = "connection-status-banner reconnecting";
        banner.classList.remove('hidden');
      }
    });

    DoubtNetAPI.on('open', () => {
      reconnectAttempts = 0;
      const banner = document.getElementById('connection-status-banner');
      if (!banner) return;

      if (_session && DoubtNetAPI.isInRoom()) {
        banner.textContent = "Connected";
        banner.className = "connection-status-banner connected";

        // Auto re-auth
        DoubtNetAPI.off('rooms_list');
        DoubtNetAPI.on('rooms_list', (data) => {
          DoubtNetAPI.off('rooms_list');
          // Auto select room
          DoubtNetAPI.off('room_entered');
          DoubtNetAPI.on('room_entered', (enteredData) => {
            DoubtNetAPI.off('room_entered');
            onAuthenticated(
              enteredData.username,
              enteredData.role,
              enteredData.state,
              enteredData.room_code,
              enteredData.room_name,
              enteredData.protocol_version
            );
            // Hide banner after 2s
            setTimeout(() => {
              banner.classList.add('hidden');
            }, 2000);
          });
          DoubtNetAPI.send({ type: 'select_room', room_code: _session.roomCode });
        });

        DoubtNetAPI.send({ type: 'login', username: _session.username, password: _session.password });
      } else {
        banner.classList.add('hidden');
      }
    });

    // Listen for reveal_leaderboard broadcast
    DoubtNetAPI.on('reveal_leaderboard', (data) => {
      UI.showScreen('leaderboard-screen');
      UI.renderPodium(data.entries || []);
      UI.confetti(document.getElementById('confetti-canvas') || document.body);
    });

    // Leaderboard close button
    const lbCloseBtn = document.getElementById('lb-close-btn');
    if (lbCloseBtn) {
      lbCloseBtn.addEventListener('click', () => {
        const prev = UI.getPreviousScreen();
        if (prev) {
          UI.showScreen(prev);
        } else {
          if (_role === 'teacher') {
            UI.showScreen('teacher-screen');
          } else if (_role === 'student') {
            UI.showScreen('student-screen');
          } else {
            UI.showScreen('landing-screen');
          }
        }
      });
    }

    window.addEventListener('error', (event) => {
      console.error('Unhandled runtime error:', event.error);
      UI.toast('An unexpected error occurred. Please refresh.', 'error');
    });

    window.addEventListener('unhandledrejection', (event) => {
      console.error('Unhandled promise rejection:', event.reason);
      UI.toast('An unexpected network error occurred. Please check connectivity.', 'error');
    });
  }

  return { init, onAuthenticated, showRoomPicker, setSession, setRoomSession, clearSession };
})();

document.addEventListener('DOMContentLoaded', App.init);
