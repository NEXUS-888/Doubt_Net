# DoubtNet — The Problem & Solution

## The Problem
In modern classrooms, students often stay silent instead of asking doubts due to peer pressure, social anxiety, and fear of judgment.
Traditional online forums are slow, lack real-time feedback, and require manual categorization, which quickly overwhelms teachers during lectures.

## The Solution
DoubtNet solves this with an anonymous, room-based, real-time doubt resolution system built specifically for classrooms.

- **Anonymity**: Students submit questions without fear, boosting classroom participation rates dramatically.
- **Dynamic Scoping**: Teachers host a private classroom using a unique 6-character room code that students join.
- **Intelligent Clustering**: DoubtNet uses TF-IDF machine learning to group similar doubts into clusters in real-time.
- **Time-Boxed Windows**: Doubt submission is scheduled or manually toggled by the teacher, preventing distraction.
- **Gamified Point System**: Students receive points when their doubts are approved and resolved, incentivizing high-quality questions.
- **Unified Server Daemon**: A single Python process runs both the static HTTP web client and the real-time WebSocket protocol.
- **Concurrency & Safety**: All files write atomically using temporary swap files, and thread locks prevent database corruption.
- **Premium Glassmorphism**: A dark-mode user interface designed with cinematic transitions, glowing highlights, and sweep gradients.

By pairing student anonymity with smart teacher moderation tools, DoubtNet bridges the communication gap between educators and students.
