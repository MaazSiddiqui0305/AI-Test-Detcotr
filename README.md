# AI-Assisted Smart Exam Proctoring & Tab Monitor

An intelligent, dual-layer online assessment proctoring framework built for B.Tech Computer Science & Engineering students. It combines **client-side browser integrity tracking** with **server & client computer vision** to deter academic malpractice in remote examinations.

---

## 🌟 Key Features

1. **Client-Side Browser Integrity Enforcement:**
   - **Page Visibility API (`visibilitychange`):** Instantly flags when a student switches tabs, opens another application, or minimizes the browser.
   - **Fullscreen Lockdown:** Prompts and locks full-screen examination mode; exiting full-screen triggers a high-severity integrity deduction.
   - **Keyboard & Clipboard Lockout:** Blocks `Ctrl+C`, `Ctrl+V`, right-clicks, Developer Tools shortcuts (`F12`, `Ctrl+Shift+I`, `Ctrl+U`).

2. **AI Vision-Based Automated Invigilation:**
   - **Face Presence Monitoring:** Continuous face tracking to ensure the student remains in front of the screen (flags missing face $>2.5$s).
   - **Multiple Persons Detection:** Flags unauthorized individuals assisting in the room.
   - **Head Pose & Gaze Deflection:** Uses 3D facial landmarks (yaw & pitch) to detect looking away (left/right/down) for extended durations.
   - **Visual Audit Trail:** Automatically captures and stores compressed snapshot evidence when violations occur.

3. **Academic Assessment Engine:**
   - 5-question Core Computer Science exam with timer and question navigation palette.
   - Real-time Heads-Up Display (HUD) showing webcam feed, integrity score, and status badges.
   - Automated grading and instant generation of the candidate's **Integrity Index**.

4. **Faculty Invigilator Dashboard:**
   - Real-time metrics: Class Average Score, Mean Integrity Index, Flagged Sessions.
   - Candidate submission records with risk level badges (Verified / Suspicious / High Risk).
   - Interactive audit modal displaying chronological violation timestamps with clickable photo evidence.

---

## 📁 Project Structure

```
ai-smart-proctor/
├── app.py                 # Flask server with REST APIs & routing
├── database.py            # SQLite schema, seeded questions & logging functions
├── proctor_vision.py      # OpenCV / MediaPipe face tracking & head pose pipeline
├── requirements.txt       # Python dependencies
├── run.bat                # 1-click startup script for Windows
├── README.md              # Project overview and quickstart guide
├── static/
│   ├── css/
│   │   ├── style.css      # Candidate portal & exam UI styling
│   │   └── dashboard.css  # Faculty admin dashboard styling
│   ├── js/
│   │   ├── exam.js        # Quiz logic, timer & anti-cheat event listeners
│   │   ├── proctor.js     # Webcam stream & frame polling controller
│   │   └── dashboard.js   # Instructor analytics & audit modal handler
│   └── uploads/           # Automatically saved violation snapshots
├── templates/
│   ├── index.html         # Candidate registration & hardware readiness diagnostics
│   ├── exam.html          # Interactive exam interface with proctor HUD
│   ├── submitted.html     # Test submission & provisional integrity review
│   └── dashboard.html     # Faculty proctoring dashboard
└── docs/
    └── PROJECT_REPORT.md  # Comprehensive academic project report
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.10+** (Ensure "Add Python to PATH" is selected during installation)
- A working webcam and modern web browser (Google Chrome, Microsoft Edge, Brave, or Firefox)

To install Python on Windows using `winget` in PowerShell:
```powershell
winget install Python.Python.3.11
```

### 2. Running the Application
You can launch the server using either method:

#### Option A: One-Click Runner (Windows)
Double-click `run.bat` inside the project folder.

#### Option B: Manual Command Line
```powershell
cd C:\Users\Asus\.gemini\antigravity\scratch\ai-smart-proctor
pip install -r requirements.txt
python app.py
```

### 3. Accessing the Portals
- **Student Exam Portal:** [http://127.0.0.1:5000](http://127.0.0.1:5000)
- **Faculty Proctoring Dashboard:** [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard)

---

## 🧪 Live Demonstration Guide (For Viva / Presentations)

To demonstrate the system to professors and evaluators:
1. Open [http://127.0.0.1:5000](http://127.0.0.1:5000). Enter a sample name (e.g., "Alex Sharma") and Roll Number (e.g., "23CSE042").
2. Check the hardware diagnostics panel to confirm the webcam is working, then click **Request Camera & Start Exam**.
3. **Trigger Test 1 (Tab Switch):** Open a new tab in your browser. Notice how the system immediately plays a warning chime and displays an integrity alert modal.
4. **Trigger Test 2 (Clipboard Lock):** Try pressing `Ctrl+C` or right-clicking on the exam question. The action is blocked, and an alert is logged.
5. **Trigger Test 3 (Head Pose / Off-screen Gaze):** Turn your head sharply to the left or right for 3 seconds. The HUD will show "Looking Left/Right" and capture a photo.
6. Answer the questions and click **Final Submit**.
7. Go to [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard). Click **Inspect Logs** next to your name to review the exact timestamps and photographic proof of the simulated violations.
