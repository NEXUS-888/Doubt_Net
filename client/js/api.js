/**
 * api.js
 * ------
 * WebSocket connection module for DoubtNet.
 * Handles connect/disconnect, send/receive, and event callbacks.
 */

const DoubtNetAPI = (() => {
  let ws = null;
  let url = '';
  const events = {};
  let reconnectTimer = null;
  let reconnectAttempt = 0;

  function connect(serverUrl) {
    url = serverUrl;
    if (ws) disconnect();

    ws = new WebSocket(url);

    ws.onopen = () => {
      console.log('[DN] Connected');
      reconnectAttempt = 0;
      emit('open');
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        emit(data.type, data);
      } catch (err) {
        console.warn('[DN] Bad message:', e.data);
      }
    };

    ws.onclose = () => {
      console.log('[DN] Disconnected');
      emit('close');
      scheduleReconnect();
    };

    ws.onerror = () => {
      console.warn('[DN] WebSocket error');
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), 30000);
    reconnectAttempt++;
    console.log(`[DN] Reconnecting in ${delay / 1000}s (attempt ${reconnectAttempt})`);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (url) connect(url);
    }, delay);
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (ws) {
      ws.onclose = null;
      ws.close();
      ws = null;
    }
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  function isOpen() {
    return ws && ws.readyState === WebSocket.OPEN;
  }

  function on(type, callback) {
    if (!events[type]) events[type] = [];
    events[type].push(callback);
  }

  function off(type, callback) {
    if (!events[type]) return;
    events[type] = events[type].filter(cb => cb !== callback);
  }

  function emit(type, data) {
    (events[type] || []).forEach(cb => cb(data));
  }

  return { connect, disconnect, send, isOpen, on, off };
})();
