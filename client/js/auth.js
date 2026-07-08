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
        UI.Modal.showConfirm(
          'About Doubtnet',
          'Doubtnet is a real-time anonymous doubt resolution board. Students can submit doubts and constructive feedback anonymously without fear of judgment. Teachers can group similar questions dynamically using AI-driven clustering, explain them in resolution sessions, and reward active participation with points.',
          () => {},
          null // alert mode
        );
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

    const joinBtn = document.getElementById('landing-join-btn');
    if (joinBtn) {
      joinBtn.addEventListener('click', () => {
        setMode(false); // Join is student login
        setRole('student');
        UI.showScreen('auth-screen');
      });
    }

    const hostBtn = document.getElementById('landing-host-btn');
    if (hostBtn) {
      hostBtn.addEventListener('click', () => {
        setMode(true); // Host is teacher register
        setRole('teacher');
        UI.showScreen('auth-screen');
      });
    }

    const backToLanding = document.getElementById('auth-back-to-landing');
    if (backToLanding) {
      backToLanding.addEventListener('click', (e) => {
        e.preventDefault();
        UI.showScreen('landing-screen');
      });
    }

    tabLogin.addEventListener('click', () => setMode(false));
    tabRegister.addEventListener('click', () => setMode(true));

    roleStudent.addEventListener('click', () => setRole('student'));
    roleTeacher.addEventListener('click', () => setRole('teacher'));

    const toggleBtn = document.getElementById('password-toggle-btn');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        toggleBtn.textContent = type === 'password' ? 'Show' : 'Hide';
      });
    }

    const toggleAdvanced = document.getElementById('toggle-advanced-settings');
    const advancedPanel = document.getElementById('advanced-settings-panel');
    if (toggleAdvanced && advancedPanel) {
      toggleAdvanced.addEventListener('click', (e) => {
        e.preventDefault();
        advancedPanel.classList.toggle('hidden');
      });
    }

    // Double click wordmark to toggle advanced settings
    const wordmarks = document.querySelectorAll('.chalk-wordmark, .chalk-wordmark-sm');
    wordmarks.forEach(wm => {
      wm.addEventListener('dblclick', () => {
        if (advancedPanel) {
          advancedPanel.classList.toggle('hidden');
          UI.toast('Advanced configuration panel toggled.', 'info');
        }
      });
    });

    authForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleSubmit();
    });
  }

  function setMode(register) {
    isRegister = register;
    tabLogin.classList.toggle('active', !register);
    tabRegister.classList.toggle('active', register);
    tabLogin.setAttribute('aria-selected', !register ? 'true' : 'false');
    tabRegister.setAttribute('aria-selected', register ? 'true' : 'false');
    roleRow.classList.toggle('hidden', !register);
    submitLabel.textContent = register ? 'Create Account' : 'Sign in';
    authError.textContent = '';
  }

  function setRole(role) {
    currentRole = role;
    roleStudent.classList.toggle('active', role === 'student');
    roleTeacher.classList.toggle('active', role === 'teacher');
    roleStudent.setAttribute('aria-selected', role === 'student' ? 'true' : 'false');
    roleTeacher.setAttribute('aria-selected', role === 'teacher' ? 'true' : 'false');
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

    // Store credentials in in-memory SessionStore
    App.setSession(username, password, currentRole);

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

  return { init, setupAuthListeners, setMode, setRole };
})();
