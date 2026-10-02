/**
 * Exam Core Controller
 * Handles Question Navigation, Anti-Cheat Listeners, Audio Alerts, and Submission
 */

let examData = null;
let currentQuestionIndex = 0;
let userAnswers = {};
let timerInterval = null;
let timeRemaining = 300; // default 5 minutes
let violationWarnings = 0;
const MAX_WARNINGS = 5;

// Audio Context for Warning Chimes
let audioCtx = null;
function playWarningBeep() {
    try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(440, audioCtx.currentTime); // A4
        osc.frequency.exponentialRampToValueAtTime(220, audioCtx.currentTime + 0.3);
        gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
        gain.gain.linearRampToValueAtTime(0.01, audioCtx.currentTime + 0.3);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.3);
    } catch (e) {
        console.log("Audio not allowed yet without user gesture.");
    }
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const submissionId = urlParams.get('submission_id');

    if (!submissionId) {
        alert("Session error: No submission ID found. Redirecting to registration.");
        window.location.href = '/';
        return;
    }

    // Attempt Fullscreen on start
    requestExamFullscreen();

    // Fetch Exam Questions
    try {
        const res = await fetch('/api/questions');
        const data = await res.json();
        if (data.success && data.questions.length > 0) {
            examData = data;
            timeRemaining = data.duration_seconds || 300;
            initExamUI();
            startTimer();
            initAntiCheatListeners(submissionId);
        } else {
            alert("No active questions available for this exam.");
        }
    } catch (err) {
        console.error("Failed to load exam:", err);
    }
});

function requestExamFullscreen() {
    const elem = document.documentElement;
    if (elem.requestFullscreen) {
        elem.requestFullscreen().catch(err => {
            console.warn("Fullscreen permission denied or blocked:", err);
        });
    }
}

function initExamUI() {
    renderPalette();
    renderQuestion(currentQuestionIndex);

    document.getElementById('prevBtn').addEventListener('click', () => {
        if (currentQuestionIndex > 0) {
            currentQuestionIndex--;
            renderQuestion(currentQuestionIndex);
            updatePaletteActive();
        }
    });

    document.getElementById('nextBtn').addEventListener('click', () => {
        if (currentQuestionIndex < examData.questions.length - 1) {
            currentQuestionIndex++;
            renderQuestion(currentQuestionIndex);
            updatePaletteActive();
        }
    });

    document.getElementById('submitBtn').addEventListener('click', () => {
        if (confirm("Are you sure you want to submit your exam now?")) {
            submitExam();
        }
    });

    document.getElementById('dismissAlertBtn').addEventListener('click', () => {
        document.getElementById('alertModal').classList.remove('active');
    });
}

function renderPalette() {
    const grid = document.getElementById('paletteGrid');
    grid.innerHTML = '';
    examData.questions.forEach((q, idx) => {
        const btn = document.createElement('button');
        btn.className = 'palette-btn';
        btn.innerText = idx + 1;
        btn.id = `palette-${idx}`;
        if (idx === 0) btn.classList.add('active');
        btn.addEventListener('click', () => {
            currentQuestionIndex = idx;
            renderQuestion(idx);
            updatePaletteActive();
        });
        grid.appendChild(btn);
    });
}

function updatePaletteActive() {
    document.querySelectorAll('.palette-btn').forEach((btn, idx) => {
        btn.classList.toggle('active', idx === currentQuestionIndex);
        const qId = examData.questions[idx].id;
        btn.classList.toggle('answered', Boolean(userAnswers[qId]));
    });
}

function renderQuestion(index) {
    const q = examData.questions[index];
    document.getElementById('qNumberDisplay').innerText = `Question ${index + 1} of ${examData.questions.length}`;
    document.getElementById('qMarksDisplay').innerText = `${q.marks} Marks`;
    document.getElementById('qTextDisplay').innerText = q.question_text;

    const optionsContainer = document.getElementById('optionsContainer');
    optionsContainer.innerHTML = '';

    const options = [
        { letter: 'A', text: q.option_a },
        { letter: 'B', text: q.option_b },
        { letter: 'C', text: q.option_c },
        { letter: 'D', text: q.option_d }
    ];

    const currentSelected = userAnswers[q.id];

    options.forEach(opt => {
        const item = document.createElement('div');
        item.className = 'option-item';
        if (currentSelected === opt.letter) item.classList.add('selected');

        item.innerHTML = `
            <div class="option-letter">${opt.letter}</div>
            <div class="option-content">${opt.text}</div>
        `;

        item.addEventListener('click', () => {
            userAnswers[q.id] = opt.letter;
            renderQuestion(index);
            updatePaletteActive();
        });

        optionsContainer.appendChild(item);
    });

    // Update button states
    document.getElementById('prevBtn').disabled = (index === 0);
    document.getElementById('nextBtn').style.display = (index === examData.questions.length - 1) ? 'none' : 'inline-flex';
    document.getElementById('submitBtn').style.display = (index === examData.questions.length - 1) ? 'inline-flex' : 'none';
}

function startTimer() {
    const timerElem = document.getElementById('timerDisplay');
    function updateClock() {
        const mins = Math.floor(timeRemaining / 60);
        const secs = timeRemaining % 60;
        timerElem.innerText = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

        if (timeRemaining <= 60) {
            timerElem.parentElement.classList.add('timer-warning');
        }

        if (timeRemaining <= 0) {
            clearInterval(timerInterval);
            alert("Time has expired! Submitting your exam automatically.");
            submitExam();
        }
        timeRemaining--;
    }
    updateClock();
    timerInterval = setInterval(updateClock, 1000);
}

// ==================== ANTI-CHEAT SECURITY CONTROLS ====================

let lastTabSwitchTimestamp = 0;

function initAntiCheatListeners(submissionId) {
    // 1. Tab Switch Detection (HTML5 Page Visibility API)
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            const now = Date.now();
            if (now - lastTabSwitchTimestamp > 2000) {
                lastTabSwitchTimestamp = now;
                triggerViolation(
                    submissionId,
                    'TAB_SWITCH',
                    'Tab switched or browser minimized during active examination.'
                );
            }
        }
    });

    // 2. Window Blur (e.g. alt-tabbing or clicking outside)
    window.addEventListener('blur', () => {
        const now = Date.now();
        if (now - lastTabSwitchTimestamp > 2000) {
            lastTabSwitchTimestamp = now;
            triggerViolation(
                submissionId,
                'TAB_SWITCH',
                'Candidate switched away from the active exam window.'
            );
        }
    });

    // 3. Fullscreen Exit Detection
    document.addEventListener('fullscreenchange', () => {
        if (!document.fullscreenElement) {
            triggerViolation(
                submissionId,
                'FULLSCREEN_EXIT',
                'Candidate exited secure full-screen examination mode.'
            );
        }
    });

    // 4. Disable Context Menu (Right Click)
    document.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        triggerViolation(
            submissionId,
            'CLIPBOARD_ATTEMPT',
            'Right-click context menu access attempted.'
        );
    });

    // 5. Disable Copy / Cut / Paste
    ['copy', 'cut', 'paste'].forEach(evtName => {
        document.addEventListener(evtName, (e) => {
            e.preventDefault();
            triggerViolation(
                submissionId,
                'CLIPBOARD_ATTEMPT',
                `Clipboard action (${evtName}) intercepted and blocked.`
            );
        });
    });

    // 6. Block DevTools Shortcuts & Common Hotkeys
    document.addEventListener('keydown', (e) => {
        // F12 or F11
        if (e.key === 'F12' || e.key === 'F11') {
            e.preventDefault();
            triggerViolation(submissionId, 'DEVTOOLS_ATTEMPT', 'Developer Tools shortcut intercepted.');
        }
        // Ctrl+Shift+I / Ctrl+Shift+J / Ctrl+U
        if (e.ctrlKey && (e.shiftKey && (e.key === 'I' || e.key === 'J' || e.key === 'C') || e.key === 'u')) {
            e.preventDefault();
            triggerViolation(submissionId, 'DEVTOOLS_ATTEMPT', 'Source inspection attempt intercepted.');
        }
    });
}

function triggerViolation(submissionId, violationType, description) {
    violationWarnings++;
    playWarningBeep();

    // Capture current webcam frame if available
    let frameData = null;
    if (window.captureProctorFrame) {
        frameData = window.captureProctorFrame();
    }

    // Display Alert Modal to candidate
    showAlertModal(violationType, description);

    // Sync violation to server
    fetch('/api/log-violation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            submission_id: submissionId,
            violation_type: violationType,
            description: description,
            image: frameData
        })
    }).then(res => res.json()).then(data => {
        if (data.updated_stats) {
            updateHUDStats(data.updated_stats.integrity_score, data.updated_stats.violations_count);
        }
    }).catch(err => console.error("Violation logging failed:", err));

    // Force Submit if warnings exceed limit
    if (violationWarnings >= MAX_WARNINGS) {
        alert("Maximum malpractice warning threshold reached. Your exam is being automatically submitted.");
        submitExam();
    }
}

function showAlertModal(title, desc) {
    const modal = document.getElementById('alertModal');
    document.getElementById('alertModalTitle').innerText = `⚠️ Integrity Warning: ${title.replace('_', ' ')}`;
    document.getElementById('alertModalDesc').innerText = desc;
    document.getElementById('alertModalCount').innerText = `Warning ${violationWarnings} of ${MAX_WARNINGS}`;
    modal.classList.add('active');

    // Auto dismiss modal after 4 seconds
    setTimeout(() => {
        modal.classList.remove('active');
    }, 4000);
}

function updateHUDStats(integrityScore, totalViolations) {
    const hudScore = document.getElementById('hudIntegrityScore');
    const hudViol = document.getElementById('hudViolationsCount');
    if (hudScore) hudScore.innerText = `${integrityScore}%`;
    if (hudViol) hudViol.innerText = totalViolations;

    const box = document.querySelector('.proctor-video-box');
    if (box) {
        box.classList.add('flagged');
        setTimeout(() => box.classList.remove('flagged'), 2500);
    }
}

// ==================== EXAM SUBMISSION ====================

async function submitExam() {
    clearInterval(timerInterval);
    const urlParams = new URLSearchParams(window.location.search);
    const submissionId = urlParams.get('submission_id');

    try {
        const res = await fetch('/api/submit-exam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                submission_id: submissionId,
                answers: userAnswers
            })
        });

        const data = await res.json();
        if (data.success) {
            window.location.href = `/submitted?submission_id=${submissionId}`;
        } else {
            alert("Error submitting exam. Please notify your invigilator.");
        }
    } catch (err) {
        console.error("Submission error:", err);
        window.location.href = `/submitted?submission_id=${submissionId}`;
    }
}
