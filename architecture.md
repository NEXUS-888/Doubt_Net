# DoubtNet Architecture Document

This document outlines the architecture, layout, design patterns, and protocols that power the **DoubtNet** real-time classroom doubt-resolution application.

---

## 🛠️ Codebase Structure

```
chatapp/
│
├── client/                     # HTML, CSS, JS static web application assets
│   ├── css/
│   │   ├── theme.css           # Styling variables, layouts, and glassmorphic designs
│   │   └── animations.css      # UI transition keyframes, glows, hover lifts, shakes
│   ├── js/
│   │   ├── api.js              # WebSocket layer, connection retries with backoff
│   │   ├── ui.js               # Shared DOM tools: toast alerts, confetti, count downs
│   │   ├── auth.js             # Authentication view state, login/registration handler
│   │   ├── student.js          # Student view: doubt editor, countdown state, my-doubts
│   │   ├── teacher.js          # Teacher view: moderation tab, schedules, cluster editor
│   │   └── app.js              # Central coordination script
│   └── index.html              # Single Page Application structure
│
├── server/                     # Async-based WebSocket & HTTP Python server
│   ├── server.py               # Main launcher: sets up WebSockets and HTTP server daemon
│   ├── chat_server.py          # WebSocket handler: connection scopes, message routing
│   ├── connection_manager.py   # Thread-safe client connection routing and broadcasting
│   ├── doubts.py               # Thread-safe doubts storage, fetching, and status updates
│   ├── schedule.py             # Classroom weekly schedule and manual override states
│   ├── points.py               # Gamified point calculation database
│   ├── users.py                # BCrypt password hashing, registration, and sessions
│   ├── rooms.py                # Room directories, unique 6-character room codes
│   ├── moderation.py           # profanity filtering and heuristics checking
│   ├── cluster.py              # ML-based TF-IDF Clustering & manual merge/split logic
│   ├── protocol.py             # Strict WebSocket JSON schemas (Single Source of Truth)
│   └── requirements.txt        # Backend dependencies
│
└── data/                       # Scoped server databases
    ├── users.json              # Global user profiles and associated room codes
    └── rooms/
        └── <ROOM_CODE>/        # Isolated directory per classroom
            ├── doubts.json
            ├── schedule.json
            └── points.json
```

---

## 🏛️ Key Design Concepts

### 1. Unified Server Daemon
- A single entry point `server.py` starts two parallel servers:
  1. An **HTTP Server** (running on port `8080` in a daemon thread) serving the static assets of the `client/` folder.
  2. An **Async WebSocket Server** (running on port `8765` using `asyncio` and `websockets`) managing all live messages.
- This allows DoubtNet to be run in any classroom with a single command without needing external reverse proxies like Nginx.

### 2. Multi-Tenant Room Isolation
- Dynamic Rooms: When a teacher registers, they input a room name (e.g. "Math 101"). The server automatically generates a unique 6-character room code (e.g. `1R5C5S`).
- Directory Isolation: All room-specific data (doubts, weekly schedules, points) is dynamically created and stored under `data/rooms/<ROOM_CODE>/`. There is no global crossover of student questions.
- Student exclusivity: Students enter the room code upon registration/login and are strictly routed to their teacher's classroom scope.

### 3. Concurrency, Locks & Safety
- **Atomic File Writes**: To prevent data loss or JSON corruption, every `_save()` function writes first to a temporary file (`.json.tmp`) and then calls `os.replace()` to atomically swap the file on disk.
- **Reentrant Locks**: Operations on `doubts.json` are wrapped with `threading.RLock()` to prevent deadlocks since recursive operations may acquire the lock multiple times on the same thread.
- **Async Thread Wrappers**: In `chat_server.py`, all synchronous blocking file I/O calls are offloaded using `asyncio.to_thread(func, *args)` to keep the main asyncio event loop responsive.

### 4. Machine Learning-based Clustering
- In `cluster.py`, when a teacher clicks "Auto-Cluster", DoubtNet checks if `scikit-learn` is installed.
- It fits the text of approved doubts using a `TfidfVectorizer` (term frequency-inverse document frequency) and computes a cosine similarity matrix.
- Similar doubts are grouped under representative text blocks to prevent the teacher from answering duplicate questions.
- A capped **10-level undo stack** is maintained to allow teachers to split or merge groups of doubts without risking memory leak.

---

## 🌐 WebSocket Protocol Schemas

Clients communicate with the server using standard JSON messages over WebSocket:

### Client ⇄ Server Actions

#### Auth & Room Handshakes
* **Client Register**: `{ type: "register", username, password, role, room_code?, room_name? }`
* **Client Login**: `{ type: "login", username, password }`
* **Server Auth OK**: `{ type: "auth_ok", username, role, state, room_code, room_name }`
* **Server Needs Room** (For legacy migration): `{ type: "needs_room", role }`

#### Doubt Workflow
* **Student Submit**: `{ type: "submit_doubt", text, urgency, day }`
* **Student Draft Autosave**: `{ type: "autosave_draft", text }`
* **Teacher Update Status**: `{ type: "update_doubt_status", id, status }`
* **Teacher Manual Override**: `{ type: "toggle_allow_all_doubts", enabled }`
* **Teacher Resolve Cluster**: `{ type: "resolve_cluster", id }`

#### Sync & Broadcasts
* **Server State Broadcast**: `{ type: "state", state }`
* **Server Presence Update**: `{ type: "presence", users }`
