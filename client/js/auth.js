/**
 * auth.js
 * -------
 * Login/register screen logic with role-aware and room-aware routing.
 */

const Auth = (() => {
  let currentRole = 'student';
  let isRegister = false;

  const authScreen = document.getElementById('auth-screen');
  const tabLogin = document.getElementById('tab-login');
  const tabRegister = document.getElementById('tab-register');
  const roleRow = document.getElementById('role-row');
  const roleStudent = document.getElementById('role-student');
  const roleTeacher = document.getElementById('role-teacher');
  const authForm = document.getElementById('auth-form');
  
  const usernameInput = document.getElementById('username-input');
  const passwordInput = document.getElementById('password-input');
  
  const roomCodeField = document.getElementById('room-code-field');
  const roomCodeInput = document.getElementById('room-code-input');
  const roomNameField = document.getElementById('room-name-field');
  const roomNameInput = document.getElementById('room-name-input');
  
  const authError = document.getElementById('auth-error');
  const submitLabel = document.getElementById('auth-submit-label');
  const serverUrlInput = document.getElementById('server-url-input');
  const brandDot = document.getElementById('brand-dot');

  // Needs Room Screen Elements
  const needsRoomScreen = document.getElementById('needs-room-screen');
  const teacherSetup = document.getElementById('teacher-setup-area');
  const studentSetup = document.getElementById('student-setup-area');
  const createRoomForm = document.getElementById('create-room-form');
  const joinRoomForm = document.getElementById('join-room-form');
  const needsRoomError = document.getElementById('needs-room-error');

  function init() {
    bindEvents();
    UI.showScreen('auth-screen');
  }

  function bindEvents() {
    tabLogin.addEventListener('click', () => setMode(false));
    tabRegister.addEventListener('click', () => setMode(true));

    roleStudent.addEventListener('click', () => setRole('student'));
    roleTeacher.addEventListener('click', () => setRole('teacher'));

    authForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleSubmit();
    });

    createRoomForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleCreateRoom();
    });

    joinRoomForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleJoinRoom();
    });
  }

  function setMode(register) {
    isRegister = register;
    tabLogin.classList.toggle('active', !register);
    tabRegister.classList.toggle('active', register);
    roleRow.classList.toggle('hidden', !register);
    submitLabel.textContent = register ? 'Create Account' : 'Connect';
    authError.textContent = '';
    
    if (!register) {
      roomCodeField.classList.add('hidden');
      roomNameField.classList.add('hidden');
    } else {
      setRole(currentRole);
    }
  }

  function setRole(role) {
    currentRole = role;
    roleStudent.classList.toggle('active', role === 'student');
    roleTeacher.classList.toggle('active', role === 'teacher');
    authError.textContent = '';
    
    if (isRegister) {
      roomCodeField.classList.toggle('hidden', role !== 'student');
      roomNameField.classList.toggle('hidden', role !== 'teacher');
    } else {
      roomCodeField.classList.add('hidden');
      roomNameField.classList.add('hidden');
    }
  }

  function handleSubmit() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    const serverUrl = serverUrlInput.value.trim();
    const roomCode = roomCodeInput.value.trim();
    const roomName = roomNameInput.value.trim();

    if (!username || !password) {
      authError.textContent = 'Fill in all fields.';
      return;
    }

    if (isRegister) {
      if (currentRole === 'student' && !roomCode) {
        authError.textContent = 'Room Code is required.';
        return;
      }
      if (currentRole === 'teacher' && !roomName) {
        authError.textContent = 'Room Name is required.';
        return;
      }
    }

    const msg = isRegister
      ? { type: 'register', username, password, role: currentRole, room_code: roomCode, room_name: roomName }
      : { type: 'login', username, password };

    brandDot.classList.remove('online');
    authError.textContent = 'Connecting...';

    // Hook listeners
    setupAuthListeners();

    DoubtNetAPI.on('open', function sendAuth() {
      DoubtNetAPI.off('open', sendAuth);
      DoubtNetAPI.send(msg);
    });

    DoubtNetAPI.connect(serverUrl);
  }

  function setupAuthListeners() {
    DoubtNetAPI.off('auth_ok');
    DoubtNetAPI.off('auth_error');
    DoubtNetAPI.off('needs_room');

    DoubtNetAPI.on('auth_ok', (data) => {
      authError.textContent = '';
      needsRoomError.textContent = '';
      brandDot.classList.add('online');
      App.onAuthenticated(data.username, data.role, data.state, data.room_code, data.room_name);
    });

    DoubtNetAPI.on('auth_error', (data) => {
      brandDot.classList.remove('online');
      authError.textContent = data.message || 'Authentication failed.';
      needsRoomError.textContent = data.message || 'Action failed.';
      if (document.getElementById('needs-room-screen').classList.contains('hidden')) {
        UI.shake('auth-card');
      } else {
        UI.shake('needs-room-card');
      }
    });

    DoubtNetAPI.on('needs_room', (data) => {
      authError.textContent = '';
      UI.showScreen('needs-room-screen');
      if (data.role === 'teacher') {
        teacherSetup.classList.remove('hidden');
        studentSetup.classList.add('hidden');
      } else {
        studentSetup.classList.remove('hidden');
        teacherSetup.classList.add('hidden');
      }
    });
  }

  function handleCreateRoom() {
    const roomName = document.getElementById('create-room-name-input').value.trim();
    if (!roomName) {
      needsRoomError.textContent = 'Room name cannot be empty.';
      return;
    }
    setupAuthListeners();
    DoubtNetAPI.send({ type: 'create_room', room_name: roomName });
  }

  function handleJoinRoom() {
    const roomCode = document.getElementById('join-room-code-input').value.trim();
    if (!roomCode) {
      needsRoomError.textContent = 'Room code cannot be empty.';
      return;
    }
    setupAuthListeners();
    DoubtNetAPI.send({ type: 'join_room', room_code: roomCode });
  }

  return { init };
})();
