import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proctor.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_no TEXT UNIQUE NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Exams table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            duration_seconds INTEGER DEFAULT 600,
            total_marks INTEGER DEFAULT 50
        )
    ''')

    # Questions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            marks INTEGER DEFAULT 10,
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
    ''')

    # Submissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_id INTEGER NOT NULL,
            score INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            integrity_score INTEGER DEFAULT 100,
            violations_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'IN_PROGRESS',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            submitted_at TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id),
            FOREIGN KEY (exam_id) REFERENCES exams (id)
        )
    ''')

    # Violations audit log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            violation_type TEXT NOT NULL,
            description TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            snapshot_filename TEXT,
            FOREIGN KEY (submission_id) REFERENCES submissions (id)
        )
    ''')

    # Seed Default Exam & CS Questions if empty
    cursor.execute("SELECT COUNT(*) FROM exams")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO exams (title, description, duration_seconds, total_marks)
            VALUES ('CSE Core Foundations Exam', 'Assessing fundamentals in Data Structures, OS, Algorithms and Web Security.', 300, 50)
        ''')
        exam_id = cursor.lastrowid

        sample_questions = [
            (
                exam_id,
                "Which data structure is primarily used to perform a Breadth-First Search (BFS) on a graph?",
                "Stack", "Queue", "Binary Search Tree", "Priority Queue",
                "B", 10
            ),
            (
                exam_id,
                "What is the average case time complexity of QuickSort?",
                "O(N^2)", "O(N)", "O(N log N)", "O(log N)",
                "C", 10
            ),
            (
                exam_id,
                "Which HTTP method is idempotent and used to retrieve representation of a resource without side effects?",
                "POST", "DELETE", "GET", "PATCH",
                "C", 10
            ),
            (
                exam_id,
                "In Operating Systems, which of the following is NOT a condition required for a Deadlock to occur?",
                "Mutual Exclusion", "Hold and Wait", "Preemption Allowed", "Circular Wait",
                "C", 10
            ),
            (
                exam_id,
                "Which HTML5 API allows a web application to detect when a user switches away from the active browser tab?",
                "Page Visibility API", "Web Storage API", "Geolocation API", "Web Notifications API",
                "A", 10
            )
        ]

        cursor.executemany('''
            INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_option, marks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_questions)

    conn.commit()
    conn.close()

def register_or_get_student(name, roll_no, email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, roll_no, email FROM students WHERE roll_no = ?", (roll_no,))
    row = cursor.fetchone()
    if row:
        student_id = row['id']
        cursor.execute("UPDATE students SET name = ?, email = ? WHERE id = ?", (name, email, student_id))
    else:
        cursor.execute("INSERT INTO students (name, roll_no, email) VALUES (?, ?, ?)", (name, roll_no, email))
        student_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return student_id

def create_submission(student_id, exam_id=1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO submissions (student_id, exam_id, status, started_at)
        VALUES (?, ?, 'IN_PROGRESS', CURRENT_TIMESTAMP)
    ''', (student_id, exam_id))
    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return submission_id

def get_questions_for_exam(exam_id=1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, question_text, option_a, option_b, option_c, option_d, marks
        FROM questions WHERE exam_id = ?
        ORDER BY id ASC
    ''', (exam_id,))
    rows = cursor.fetchall()
    if not rows:
        cursor.execute('''
            SELECT id, question_text, option_a, option_b, option_c, option_d, marks
            FROM questions
            ORDER BY id ASC
        ''')
        rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def log_violation(submission_id, violation_type, description, snapshot_filename=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO violations (submission_id, violation_type, description, snapshot_filename, timestamp)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (submission_id, violation_type, description, snapshot_filename))

    # Calculate penalty based on violation severity
    # Tab switch: -10, Multiple faces: -15, Face missing >3s: -12, Looking away: -5, Copy/Paste: -8
    penalty_map = {
        'TAB_SWITCH': 10,
        'MULTIPLE_FACES': 15,
        'FACE_MISSING': 12,
        'LOOKING_AWAY': 5,
        'FULLSCREEN_EXIT': 10,
        'CLIPBOARD_ATTEMPT': 8,
        'DEVTOOLS_ATTEMPT': 15
    }
    penalty = penalty_map.get(violation_type, 5)

    cursor.execute('''
        UPDATE submissions
        SET violations_count = violations_count + 1,
            integrity_score = MAX(0, integrity_score - ?)
        WHERE id = ?
    ''', (penalty, submission_id))

    conn.commit()
    
    # Return updated score
    cursor.execute("SELECT integrity_score, violations_count FROM submissions WHERE id = ?", (submission_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {'integrity_score': 100, 'violations_count': 0}

def submit_exam_answers(submission_id, user_answers):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT exam_id FROM submissions WHERE id = ?", (submission_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    exam_id = row['exam_id']

    cursor.execute("SELECT id, correct_option, marks FROM questions WHERE exam_id = ?", (exam_id,))
    questions = cursor.fetchall()

    total_score = 0
    total_questions = len(questions)

    answers_dict = user_answers if isinstance(user_answers, dict) else {}

    for q in questions:
        q_id = str(q['id'])
        raw_val = answers_dict.get(q_id)
        chosen = str(raw_val).strip().upper() if raw_val is not None else ''
        correct = str(q['correct_option']).strip().upper() if q['correct_option'] is not None else ''
        if chosen and chosen == correct:
            total_score += q['marks']

    cursor.execute('''
        UPDATE submissions
        SET score = ?,
            total_questions = ?,
            status = 'COMPLETED',
            submitted_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (total_score, total_questions, submission_id))

    conn.commit()
    conn.close()
    return get_submission_summary(submission_id)

def get_submission_summary(submission_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.score, s.total_questions, s.integrity_score, s.violations_count, s.status,
               s.started_at, s.submitted_at,
               COALESCE(st.name, 'Candidate') as student_name,
               COALESCE(st.roll_no, 'N/A') as roll_no,
               COALESCE(st.email, '') as email,
               COALESCE(e.title, 'CSE Core Exam') as exam_title,
               COALESCE(e.total_marks, 50) as total_marks
        FROM submissions s
        LEFT JOIN students st ON s.student_id = st.id
        LEFT JOIN exams e ON s.exam_id = e.id
        WHERE s.id = ?
    ''', (submission_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_dashboard_submissions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.id, s.score, s.total_questions, s.integrity_score, s.violations_count, s.status,
               s.started_at, s.submitted_at,
               COALESCE(st.name, 'Candidate') as student_name,
               COALESCE(st.roll_no, 'N/A') as roll_no,
               COALESCE(st.email, '') as email,
               COALESCE(e.title, 'CSE Core Exam') as exam_title,
               COALESCE(e.total_marks, 50) as total_marks
        FROM submissions s
        LEFT JOIN students st ON s.student_id = st.id
        LEFT JOIN exams e ON s.exam_id = e.id
        ORDER BY s.id DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_submission_violations(submission_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, violation_type, description, timestamp, snapshot_filename
        FROM violations
        WHERE submission_id = ?
        ORDER BY id DESC
    ''', (submission_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
