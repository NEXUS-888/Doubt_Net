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
  let intentionalDisconnect = false;
  let inRoom = false; // only auto-reconnect once user has entered a room

  function connect(serverUrl) {
    url = serverUrl;
    intentionalDisconnect = false;
    if (ws) disconnect();

    const socket = new WebSocket(url);
    ws = socket;

    socket.onopen = () => {
      // Ignore events from stale WebSocket instances
      if (ws !== socket) return;
      console.log('[DN] Connected');
      reconnectAttempt = 0;
      emit('open');
    };

    socket.onmessage = (e) => {
      if (ws !== socket) return;
      try {
        const data = JSON.parse(e.data);
        emit(data.type, data);
      } catch (err) {
        console.warn('[DN] Bad message:', e.data);
      }
    };

    socket.onclose = (event) => {
      // Ignore close events from old/stale WebSocket instances
      if (ws !== socket) {
        console.log('[DN] Stale WebSocket closed — ignoring');
        return;
      }
      console.log(`[DN] Disconnected (code=${event.code}, reason=${event.reason || 'n/a'}, clean=${event.wasClean})`);
      ws = null;
      emit('close');
      // Only auto-reconnect if the disconnect was unexpected AND we were in a room
      if (!intentionalDisconnect && inRoom) {
        scheduleReconnect();
      }
    };

    socket.onerror = () => {
      if (ws !== socket) return;
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
    intentionalDisconnect = true;
    inRoom = false;
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

  function setInRoom(value) {
    inRoom = value;
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
      return true;
    }
    return false;
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
    if (!callback) {
      delete events[type];
    } else {
      events[type] = events[type].filter(cb => cb !== callback);
    }
  }

  function emit(type, data) {
    (events[type] || []).forEach(cb => cb(data));
  }

  return { connect, disconnect, send, isOpen, on, off, setInRoom };
})();
