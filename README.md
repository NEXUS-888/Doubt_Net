# DoubtNet — Real-Time Classroom Doubt Resolution

DoubtNet is a classroom doubt resolution application built on a real-time WebSocket protocol and a modern, glassmorphic visual system. It enables students to ask doubts anonymously during lectures, while teachers moderate, schedule, and cluster similar questions using built-in machine learning.

---

## 🚀 Getting Started

### 1. Installation
In the project root, navigate to the `server/` folder and install dependencies:
```bash
cd server
pip install -r requirements.txt
```

### 2. Launch
Start the unified backend server daemon:
```bash
python server.py
```
This command starts:
- The static HTTP web server on **`http://0.0.0.0:8080`** (serving the client client files).
- The live WebSocket gateway on **`ws://0.0.0.0:8765`**.

### 3. Usage
Open a web browser on any device in the classroom network and navigate to **`http://<SERVER_IP>:8080`** (e.g. `http://10.136.99.209:8080`).

---

## 💡 Key Features

- **Anonymous doubt submissions** to boost student participation rates.
- **Dynamic classrooms** hosted under unique 6-character room codes.
- **Intelligent clustering** using term frequency (TF-IDF) & Cosine Similarity.
- **Weekly class schedules** and manual overrides ("Allow All Doubts").
- **Gamified points calculations** for active and resolved students.
- **Premium design** with interactive shake notifications and shimmer logo animations.

---

## 📂 Architecture Map

For a full understanding of the architecture, data schemas, and design constraints, please refer to the dedicated **[Architecture Document](architecture.md)**.
