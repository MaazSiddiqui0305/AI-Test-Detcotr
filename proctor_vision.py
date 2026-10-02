import os
import time
import base64
import threading
import numpy as np
from io import BytesIO
from PIL import Image

# Directories
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(CURRENT_DIR, 'static', 'uploads')
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Vision Lock for MediaPipe C++ thread-safety in Flask
vision_lock = threading.Lock()

# Flags for optional vision packages
HAS_CV2 = False
HAS_MEDIAPIPE = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    pass

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
except ImportError:
    pass

# Initialize OpenCV Haar Cascade once globally if available
face_cascade = None
if HAS_CV2:
    try:
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
    except Exception as e:
        print(f"[Vision Engine] OpenCV CascadeClassifier init warning: {e}")

# Initialize MediaPipe Face Mesh if available
mp_face_mesh = None
face_mesh = None

if HAS_MEDIAPIPE:
    try:
        mp_face_mesh = mp.solutions.face_mesh
        face_mesh = mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=4,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
    except Exception as e:
        print(f"[Vision Engine] MediaPipe init warning: {e}")

# In-memory tracking for temporal buffering (to avoid false positives on sudden blinks/glances)
# Maps submission_id -> { 'consecutive_away': int, 'consecutive_missing': int, 'consecutive_multi': int }
TRACKING_SESSIONS = {}

def decode_base64_image(base64_str):
    """Decodes a data URL base64 image into RGB numpy array and PIL Image."""
    if not base64_str or not isinstance(base64_str, str):
        raise ValueError("Invalid base64 image string provided.")
    if ',' in base64_str:
        base64_str = base64_str.split(',', 1)[1]
    # Ensure proper base64 padding
    missing_padding = len(base64_str) % 4
    if missing_padding:
        base64_str += '=' * (4 - missing_padding)
    image_bytes = base64.b64decode(base64_str)
    pil_img = Image.open(BytesIO(image_bytes)).convert('RGB')
    np_img = np.array(pil_img)
    return np_img, pil_img

def save_violation_snapshot(pil_img, submission_id, violation_type):
    """Saves a compressed JPEG snapshot for visual audit evidence."""
    if not pil_img:
        return None
    timestamp_str = int(time.time() * 1000)
    v_type_str = str(violation_type or 'unspecified').lower()
    filename = f"viol_{submission_id}_{v_type_str}_{timestamp_str}.jpg"
    filepath = os.path.join(UPLOADS_DIR, filename)
    try:
        # Resize snapshot slightly to save disk space
        copy_img = pil_img.copy()
        copy_img.thumbnail((480, 360))
        copy_img.save(filepath, "JPEG", quality=75)
        return filename
    except Exception as e:
        print(f"[Vision] Snapshot save error: {e}")
        return None

def analyze_frame(submission_id, base64_str):
    """
    Analyzes an incoming frame for:
    1. Face Count (0 = Missing, 1 = Normal, >1 = Multiple Faces)
    2. Head Pose / Direction (Looking Center, Looking Left, Looking Right, Looking Down)
    
    Returns dict:
      {
        'status': 'OK' | 'VIOLATION',
        'violation_type': None | str,
        'description': None | str,
        'face_count': int,
        'gaze_direction': str,
        'snapshot_filename': str | None
      }
    """
    sub_key = str(submission_id)
    if sub_key not in TRACKING_SESSIONS:
        TRACKING_SESSIONS[sub_key] = {
            'consecutive_away': 0,
            'consecutive_missing': 0,
            'consecutive_multi': 0
        }
    session = TRACKING_SESSIONS[sub_key]

    try:
        np_img, pil_img = decode_base64_image(base64_str)
    except Exception as e:
        return {
            'status': 'ERROR',
            'error': f'Invalid image: {str(e)}',
            'face_count': 1,
            'gaze_direction': 'CENTER'
        }

    face_count = 1
    gaze_direction = 'CENTER'
    violation_type = None
    description = None
    snapshot_filename = None
    vision_processed = False

    # 1. Analyze with MediaPipe Face Mesh if available
    if HAS_MEDIAPIPE and face_mesh is not None:
        try:
            with vision_lock:
                results = face_mesh.process(np_img)
            if results and results.multi_face_landmarks:
                face_count = len(results.multi_face_landmarks)
                
                # Check head orientation on primary face
                primary_face = results.multi_face_landmarks[0]

                # Key 2D landmarks (normalized coordinates)
                # Nose tip: 1, Left cheek/eye: 234, Right cheek/eye: 454, Forehead: 10, Chin: 152
                nose = primary_face.landmark[1]
                left_edge = primary_face.landmark[234]
                right_edge = primary_face.landmark[454]
                chin = primary_face.landmark[152]
                forehead = primary_face.landmark[10]

                # Horizontal ratio (Yaw proxy)
                dist_left = abs(nose.x - left_edge.x)
                dist_right = abs(nose.x - right_edge.x)
                total_w = dist_left + dist_right

                if total_w > 0:
                    ratio = dist_left / total_w
                    if ratio < 0.32:
                        gaze_direction = 'LOOKING_RIGHT'
                    elif ratio > 0.68:
                        gaze_direction = 'LOOKING_LEFT'
                    else:
                        gaze_direction = 'CENTER'

                # Vertical ratio (Pitch proxy)
                dist_top = abs(nose.y - forehead.y)
                dist_bottom = abs(chin.y - nose.y)
                total_h = dist_top + dist_bottom
                if total_h > 0:
                    pitch_ratio = dist_top / total_h
                    if pitch_ratio > 0.72:
                        gaze_direction = 'LOOKING_DOWN'
            else:
                face_count = 0
                gaze_direction = 'UNKNOWN'
            vision_processed = True
        except Exception as e:
            print(f"[Vision] MediaPipe processing error: {e}")
            vision_processed = False

    # 2. Fallback to OpenCV Haar Cascade if MediaPipe was unavailable or failed
    if not vision_processed and HAS_CV2 and face_cascade is not None:
        try:
            gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(60, 60))
            face_count = len(faces)
            gaze_direction = 'CENTER' if face_count > 0 else 'UNKNOWN'
            vision_processed = True
        except Exception as e:
            print(f"[Vision] OpenCV fallback error: {e}")

    # --- Anomaly & Temporal Threshold Logic ---
    # Case A: Multiple Faces
    if face_count > 1:
        session['consecutive_multi'] += 1
        if session['consecutive_multi'] >= 2:  # Persists across 2 polling cycles
            violation_type = 'MULTIPLE_FACES'
            description = f"Multiple individuals detected in camera frame ({face_count} faces visible)."
            snapshot_filename = save_violation_snapshot(pil_img, submission_id, violation_type)
            session['consecutive_multi'] = 0
    else:
        session['consecutive_multi'] = 0

    # Case B: No Face Detected
    if face_count == 0:
        session['consecutive_missing'] += 1
        if session['consecutive_missing'] >= 2:  # ~3 seconds absence
            violation_type = 'FACE_MISSING'
            description = "Candidate is not visible in front of the camera."
            snapshot_filename = save_violation_snapshot(pil_img, submission_id, violation_type)
            session['consecutive_missing'] = 0
    else:
        session['consecutive_missing'] = 0

    # Case C: Looking Away (Left / Right / Down)
    if gaze_direction in ('LOOKING_LEFT', 'LOOKING_RIGHT', 'LOOKING_DOWN'):
        session['consecutive_away'] += 1
        if session['consecutive_away'] >= 3:  # ~4.5 seconds sustained gaze deflection
            violation_type = 'LOOKING_AWAY'
            description = f"Prolonged off-screen attention detected ({gaze_direction.replace('_', ' ').title()})."
            snapshot_filename = save_violation_snapshot(pil_img, submission_id, violation_type)
            session['consecutive_away'] = 0
    else:
        session['consecutive_away'] = 0

    return {
        'status': 'VIOLATION' if violation_type else 'OK',
        'violation_type': violation_type,
        'description': description,
        'face_count': face_count,
        'gaze_direction': gaze_direction,
        'snapshot_filename': snapshot_filename
    }
