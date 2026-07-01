/**
 * app.js
 * ------
 * Entrypoint for DoubtNet. Routes authenticated users to
 * student or teacher dashboard based on role and passes room details.
 */

const App = (() => {
  function onAuthenticated(username, role, state, roomCode, roomName) {
    if (role === 'teacher') {
      Teacher.start(username, roomCode, roomName);
    } else {
      Student.start(username, state, roomCode, roomName);
    }
  }

  function init() {
    Theme.init();
    Auth.init();
  }

  return { init, onAuthenticated };
})();

document.addEventListener('DOMContentLoaded', App.init);
