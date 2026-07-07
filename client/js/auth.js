/**
 * auth.js
 * -------
 * Login/register screen logic with role-aware routing.
 * After login/register, server sends rooms_list -> app.js renders picker.
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
  
  const authError = document.getElementById('auth-error');
  const submitLabel = document.getElementById('auth-submit-label');
  const serverUrlInput = document.getElementById('server-url-input');
  const brandDot = document.getElementById('brand-dot');

  function init() {
    if (serverUrlInput) {
      const ip = window.SERVER_IP || '10.136.99.209';
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      serverUrlInput.value = `${wsProtocol}://${ip}:8765`;
    }
    bindEvents();
    UI.showScreen('landing-screen');
  }

  function bindEvents() {
    // Landing screen handlers
    const aboutBtn = document.getElementById('landing-about-btn');
    if (aboutBtn) {
      aboutBtn.addEventListener('click', () => {
        UI.toast('DoubtNet is a real-time anonymous doubt resolution board.', 'info', 4000);
      });
    }

    const loginBtn = document.getElementById('landing-login-btn');
    if (loginBtn) {
      loginBtn.addEventListener('click', () => {
        setMode(false);
        UI.showScreen('auth-screen');
      });
    }

    const signupBtn = document.getElementById('landing-signup-btn');
    if (signupBtn) {
      signupBtn.addEventListener('click', () => {
        setMode(true);
        UI.showScreen('auth-screen');
      });
    }

    const startBtn = document.getElementById('landing-start-btn');
    if (startBtn) {
      startBtn.addEventListener('click', () => {
        setMode(false);
        UI.showScreen('auth-screen');
      });
    }

    tabLogin.addEventListener('click', () => setMode(false));
    tabRegister.addEventListener('click', () => setMode(true));

    roleStudent.addEventListener('click', () => setRole('student'));
    roleTeacher.addEventListener('click', () => setRole('teacher'));

    authForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleSubmit();
    });
  }

  function setMode(register) {
    isRegister = register;
    tabLogin.classList.toggle('active', !register);
    tabRegister.classList.toggle('active', register);
    roleRow.classList.toggle('hidden', !register);
    submitLabel.textContent = register ? 'Create Account' : 'Connect';
    authError.textContent = '';
  }

  function setRole(role) {
    currentRole = role;
    roleStudent.classList.toggle('active', role === 'student');
    roleTeacher.classList.toggle('active', role === 'teacher');
    authError.textContent = '';
  }

  function handleSubmit() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    const serverUrl = serverUrlInput.value.trim();

    if (!username || !password) {
      authError.textContent = 'Fill in all fields.';
      return;
    }

    const usernameRegex = /^[a-zA-Z0-9_\-]+$/;
    if (username.length < 3 || username.length > 20) {
      authError.textContent = 'Username must be 3-20 characters.';
      UI.shake('auth-card');
      return;
    }
    if (!usernameRegex.test(username)) {
      authError.textContent = 'Username can only contain letters, numbers, _ and -.';
      UI.shake('auth-card');
      return;
    }

    if (password.length < 6) {
      authError.textContent = 'Password must be at least 6 characters.';
      UI.shake('auth-card');
      return;
    }
    if (isRegister) {
      const hasLetter = /[a-zA-Z]/.test(password);
      const hasNumber = /[0-9]/.test(password);
      if (!hasLetter || !hasNumber) {
        authError.textContent = 'Password must contain both letters and numbers.';
        UI.shake('auth-card');
        return;
      }
    }

    const msg = isRegister
      ? { type: 'register', username, password, role: currentRole }
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
    DoubtNetAPI.off('auth_error');
    DoubtNetAPI.off('rooms_list');

    DoubtNetAPI.on('rooms_list', (data) => {
      authError.textContent = '';
      brandDot.classList.add('online');
      if (data.protocol_version && data.protocol_version !== 'v1.2') {
        console.warn('Protocol version mismatch! Client: v1.2, Server: ' + data.protocol_version);
      }
      App.showRoomPicker(data.username, data.role, data.rooms);
    });

    DoubtNetAPI.on('auth_error', (data) => {
      brandDot.classList.remove('online');
      authError.textContent = data.message || 'Authentication failed.';
      const pickerError = document.getElementById('picker-error');
      if (pickerError) pickerError.textContent = data.message || 'Action failed.';
      
      if (!document.getElementById('room-picker-screen').classList.contains('hidden')) {
        UI.shake('room-picker-screen');
      } else {
        UI.shake('auth-card');
      }
    });
  }

  return { init, setupAuthListeners };
})();
