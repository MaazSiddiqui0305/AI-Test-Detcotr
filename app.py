import os
import json
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from flask_cors import CORS
from database import (
    init_db, register_or_get_student, create_submission,
    get_questions_for_exam, log_violation, submit_exam_answers,
    get_submission_summary, get_all_dashboard_submissions,
    get_submission_violations
)
from proctor_vision import analyze_frame, save_violation_snapshot, decode_base64_image

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Ensure database is initialized on startup
init_db()

@app.route('/')
def index():
    """Registration and Hardware Readiness Check."""
    return render_template('index.html')

@app.route('/exam')
def exam_page():
    """Secure Proctored Exam Interface."""
    submission_id = request.args.get('submission_id')
    if not submission_id:
        return redirect(url_for('index'))
    return render_template('exam.html', submission_id=submission_id)

@app.route('/submitted')
def submitted_page():
    """Post-exam review and integrity score report."""
    submission_id = request.args.get('submission_id')
    if not submission_id:
        return redirect(url_for('index'))
    summary = get_submission_summary(submission_id)
    return render_template('submitted.html', summary=summary)

@app.route('/dashboard')
def dashboard_page():
    """Faculty / Admin Proctoring Analytics Portal."""
    return render_template('dashboard.html')

# ==================== API ENDPOINTS ====================

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    roll_no = data.get('roll_no', '').strip().upper()
    email = data.get('email', '').strip()

    if not name or not roll_no:
        return jsonify({'error': 'Name and Roll Number are required.'}), 400

    student_id = register_or_get_student(name, roll_no, email)
    submission_id = create_submission(student_id, exam_id=1)

    return jsonify({
        'success': True,
        'student_id': student_id,
        'submission_id': submission_id,
        'student_name': name,
        'roll_no': roll_no
    })

@app.route('/api/questions', methods=['GET'])
def api_questions():
    exam_id = request.args.get('exam_id', 1, type=int)
    questions = get_questions_for_exam(exam_id)
    return jsonify({
        'success': True,
        'exam_title': 'CSE Core Foundations Exam',
        'duration_seconds': 300, # 5 minutes for demo
        'questions': questions
    })

@app.route('/api/verify-frame', methods=['POST'])
def api_verify_frame():
    data = request.get_json() or {}
    submission_id = data.get('submission_id')
    image_base64 = data.get('image')

    if not submission_id or not image_base64:
        return jsonify({'error': 'submission_id and image frame required.'}), 400

    # Process frame with computer vision pipeline
    result = analyze_frame(submission_id, image_base64)

    updated_stats = None
    if result.get('status') == 'VIOLATION' and result.get('violation_type'):
        updated_stats = log_violation(
            submission_id=submission_id,
            violation_type=result['violation_type'],
            description=result['description'],
            snapshot_filename=result.get('snapshot_filename')
        )

    return jsonify({
        'success': True,
        'vision': result,
        'updated_stats': updated_stats
    })

@app.route('/api/log-violation', methods=['POST'])
def api_log_violation():
    data = request.get_json() or {}
    submission_id = data.get('submission_id')
    violation_type = data.get('violation_type', 'UNSPECIFIED')
    description = data.get('description', 'Client security event triggered.')
    image_base64 = data.get('image')

    if not submission_id:
        return jsonify({'error': 'submission_id required.'}), 400

    snapshot_filename = None
    if image_base64:
        try:
            _, pil_img = decode_base64_image(image_base64)
            snapshot_filename = save_violation_snapshot(pil_img, submission_id, violation_type)
        except Exception as e:
            print(f"[API] Failed to save snapshot for client violation: {e}")

    updated_stats = log_violation(
        submission_id=submission_id,
        violation_type=violation_type,
        description=description,
        snapshot_filename=snapshot_filename
    )

    return jsonify({
        'success': True,
        'violation_type': violation_type,
        'updated_stats': updated_stats
    })

@app.route('/api/submit-exam', methods=['POST'])
def api_submit_exam():
    data = request.get_json() or {}
    submission_id = data.get('submission_id')
    answers = data.get('answers', {})

    if not submission_id:
        return jsonify({'error': 'submission_id required.'}), 400

    summary = submit_exam_answers(submission_id, answers)
    if not summary:
        return jsonify({'error': 'Submission not found.'}), 404

    return jsonify({
        'success': True,
        'summary': summary
    })

@app.route('/api/dashboard-data', methods=['GET'])
def api_dashboard_data():
    submissions = get_all_dashboard_submissions()
    total_students = len(submissions)
    total_score = sum(s['score'] for s in submissions) if total_students else 0
    avg_score = round(total_score / total_students, 1) if total_students else 0
    
    total_integrity = sum(s['integrity_score'] for s in submissions) if total_students else 0
    avg_integrity = round(total_integrity / total_students, 1) if total_students else 100

    flagged_sessions = sum(1 for s in submissions if s['integrity_score'] < 75)

    return jsonify({
        'success': True,
        'metrics': {
            'total_students': total_students,
            'avg_score': avg_score,
            'avg_integrity': avg_integrity,
            'flagged_sessions': flagged_sessions
        },
        'submissions': submissions
    })

@app.route('/api/submission/<int:submission_id>/violations', methods=['GET'])
def api_submission_violations(submission_id):
    violations = get_submission_violations(submission_id)
    summary = get_submission_summary(submission_id)
    return jsonify({
        'success': True,
        'summary': summary,
        'violations': violations
    })

@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(os.path.join(app.static_folder, 'uploads'), filename)

if __name__ == '__main__':
    print("\n" + "="*60)
    print(" 🚀 AI-Assisted Smart Exam Proctoring System")
    print(" Local server running at: http://127.0.0.1:5000")
    print(" Instructor Dashboard:    http://127.0.0.1:5000/dashboard")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
