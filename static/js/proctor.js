/**
 * Proctor Vision & Stream Controller
 * Connects webcam, grabs periodic snapshots, sends to server vision engine,
 * and updates live HUD indicators.
 */

let videoElement = null;
let captureCanvas = null;
let captureCtx = null;
let proctorInterval = null;
let submissionId = null;

document.addEventListener('DOMContentLoaded', () => {
    videoElement = document.getElementById('examVideo');
    if (!videoElement) return; // Not on exam page

    const urlParams = new URLSearchParams(window.location.search);
    submissionId = urlParams.get('submission_id');

    // Create offscreen canvas for frame extraction
    captureCanvas = document.createElement('canvas');
    captureCanvas.width = 480;
    captureCanvas.height = 360;
    captureCtx = captureCanvas.getContext('2d');

    // Initialize Webcam
    initWebcam();
});

async function initWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 480 },
                height: { ideal: 360 },
                facingMode: 'user'
            },
            audio: false
        });

        videoElement.srcObject = stream;
        await videoElement.play();

        // Start Periodic Vision Polling (every 1.8 seconds)
        startVisionPolling();
    } catch (err) {
        console.error("Camera access failed:", err);
        alert("Camera access is mandatory for this proctored examination. Please grant camera permissions and reload.");
    }
}

/**
 * Global function to capture instantaneous video frame as JPEG base64
 */
window.captureProctorFrame = function () {
    if (!videoElement || !captureCtx || videoElement.readyState < 2) return null;
    captureCtx.drawImage(videoElement, 0, 0, captureCanvas.width, captureCanvas.height);
    return captureCanvas.toDataURL('image/jpeg', 0.7);
};

function startVisionPolling() {
    if (proctorInterval) clearInterval(proctorInterval);

    proctorInterval = setInterval(async () => {
        if (!submissionId) return;

        const frameData = window.captureProctorFrame();
        if (!frameData) return;

        try {
            const res = await fetch('/api/verify-frame', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    submission_id: submissionId,
                    image: frameData
                })
            });

            const data = await res.json();
            if (data.success && data.vision) {
                updateHUDVisionIndicators(data.vision);
                if (data.updated_stats) {
                    updateHUDStats(data.updated_stats.integrity_score, data.updated_stats.violations_count);
                }
            }
        } catch (err) {
            // Server offline or network blip - continue gracefully
            console.debug("Frame verification skipped:", err);
        }
    }, 1800);
}

function updateHUDVisionIndicators(vision) {
    const faceBadge = document.getElementById('hudFaceStatus');
    const gazeBadge = document.getElementById('hudGazeStatus');

    if (faceBadge) {
        if (vision.face_count === 1) {
            faceBadge.innerText = '1 Face (OK)';
            faceBadge.className = 'status-val val-ok';
        } else if (vision.face_count === 0) {
            faceBadge.innerText = '⚠️ No Face';
            faceBadge.className = 'status-val val-danger';
        } else {
            faceBadge.innerText = `⚠️ Multi (${vision.face_count})`;
            faceBadge.className = 'status-val val-danger';
        }
    }

    if (gazeBadge) {
        if (vision.gaze_direction === 'CENTER') {
            gazeBadge.innerText = 'Direct (OK)';
            gazeBadge.className = 'status-val val-ok';
        } else if (vision.gaze_direction === 'LOOKING_LEFT') {
            gazeBadge.innerText = 'Looking Left';
            gazeBadge.className = 'status-val val-warn';
        } else if (vision.gaze_direction === 'LOOKING_RIGHT') {
            gazeBadge.innerText = 'Looking Right';
            gazeBadge.className = 'status-val val-warn';
        } else if (vision.gaze_direction === 'LOOKING_DOWN') {
            gazeBadge.innerText = 'Looking Down';
            gazeBadge.className = 'status-val val-warn';
        } else {
            gazeBadge.innerText = 'Detecting...';
            gazeBadge.className = 'status-val';
        }
    }

    // Trigger on-screen warning if vision engine flagged a violation
    if (vision.status === 'VIOLATION' && vision.violation_type) {
        playWarningBeep();
        showAlertModal(vision.violation_type, vision.description);
    }
}
