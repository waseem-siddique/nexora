"""SQLite persistence and isolated, explicitly synthetic demo workspaces."""
from __future__ import annotations
import json
import os
import secrets
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
from .domain import COURSES, risk_for, orchestrate, today

ROOT = Path(__file__).resolve().parents[1]

def now():
    return datetime.now(timezone.utc).isoformat()

def db_path():
    return Path(os.environ.get('NEXORA_DB', os.environ.get('AXIOM_DB', str(ROOT / 'data' / 'nexora.sqlite3'))))

def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600_000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'

def check_password(password, encoded):
    try:
        _, iterations, salt, saved = encoded.split('$')
        check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
        return secrets.compare_digest(saved, check)
    except (ValueError, AttributeError):
        return False

def defaults():
    return {'provider': os.environ.get('AI_PROVIDER', 'rules'),
            'model': os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash'),
            'consent': False, 'weekly_digest': True}

def init_db():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
          password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'faculty',
          student_id INTEGER, institution TEXT NOT NULL DEFAULT 'KITS, Singapur',

          department TEXT NOT NULL DEFAULT 'Computer Science & Engineering',
          bio TEXT NOT NULL DEFAULT '', is_demo INTEGER NOT NULL DEFAULT 0,
          settings TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS students(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          name TEXT NOT NULL, roll TEXT NOT NULL, semester INTEGER NOT NULL, section TEXT NOT NULL,
          reg_no TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '',
          current_cgpa REAL, target_cgpa REAL NOT NULL DEFAULT 8.5,
          synthetic INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL, UNIQUE(user_id, roll));
        CREATE TABLE IF NOT EXISTS evidence(
          id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
          course TEXT NOT NULL, assessment_type TEXT NOT NULL DEFAULT 'Assessment',
          score REAL NOT NULL, attendance REAL NOT NULL, completion REAL NOT NULL,
          topic TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', recorded_on TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS plans(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
          course TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Draft', revision INTEGER NOT NULL DEFAULT 1,
          parent_id INTEGER REFERENCES plans(id) ON DELETE SET NULL,
          data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS progress(
          id INTEGER PRIMARY KEY, plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
          evidence_id INTEGER NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
          score REAL NOT NULL, attendance REAL NOT NULL, completion REAL NOT NULL,
          notes TEXT NOT NULL DEFAULT '', recorded_on TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS activity(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          title TEXT NOT NULL, detail TEXT NOT NULL, entity_type TEXT, entity_id INTEGER,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS academic_files(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          file_name TEXT NOT NULL, category TEXT NOT NULL, mime_type TEXT NOT NULL,
          size_bytes INTEGER NOT NULL, storage_path TEXT NOT NULL, audience TEXT NOT NULL DEFAULT 'all',
          semester INTEGER, section TEXT, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE,
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reports(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
          title TEXT NOT NULL, data TEXT NOT NULL, shared INTEGER NOT NULL DEFAULT 0,
          shared_at TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications(
          id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          title TEXT NOT NULL, detail TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'info',
          entity_type TEXT, entity_id INTEGER, read_at TEXT, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_students_owner ON students(user_id);
        CREATE INDEX IF NOT EXISTS idx_evidence_student ON evidence(student_id,recorded_on);
        CREATE INDEX IF NOT EXISTS idx_plans_owner ON plans(user_id);
        CREATE INDEX IF NOT EXISTS idx_progress_plan ON progress(plan_id);
        CREATE INDEX IF NOT EXISTS idx_users_role_student ON users(role,student_id);
        CREATE INDEX IF NOT EXISTS idx_files_owner ON academic_files(user_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_reports_student ON reports(student_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,created_at);
        ''')
        # Lightweight migrations for older local prototype databases.
        for statement in [
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'faculty'",
            "ALTER TABLE users ADD COLUMN student_id INTEGER",
            "ALTER TABLE students ADD COLUMN reg_no TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE students ADD COLUMN phone TEXT NOT NULL DEFAULT ''",
            "ALTER TABLE students ADD COLUMN current_cgpa REAL",
            "ALTER TABLE students ADD COLUMN target_cgpa REAL NOT NULL DEFAULT 8.5",
            "ALTER TABLE evidence ADD COLUMN assessment_type TEXT NOT NULL DEFAULT 'Assessment'",
        ]:
            try:
                db.execute(statement)
            except sqlite3.OperationalError:
                pass
        db.execute("UPDATE users SET role='faculty' WHERE role IS NULL OR role=''")
        db.execute("CREATE INDEX IF NOT EXISTS idx_users_email_role ON users(email,role)")
        # Repair any old sample schema naming without breaking existing data.
                # Demo accounts never share a known credential. Expire abandoned sample workspaces.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        db.execute('DELETE FROM users WHERE is_demo=1 AND created_at < ?', (cutoff,))
    try:
        os.chmod(db_path(), 0o600)
    except OSError:
        pass

def public_user(row):
    return {k: row[k] for k in ['id', 'email', 'name', 'role', 'student_id', 'institution', 'department', 'bio', 'is_demo', 'created_at']}

def log(db, user_id, title, detail='', entity_type=None, entity_id=None):
    db.execute('INSERT INTO activity(user_id,title,detail,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?)',
               (user_id, title, detail, entity_type, entity_id, now()))

def add_student(db, uid, data, synthetic=0):
    sid = db.execute('INSERT INTO students(user_id,name,roll,semester,section,reg_no,email,phone,current_cgpa,target_cgpa,synthetic,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                      (uid, data['name'], data['roll'], data['semester'], data['section'], data.get('reg_no',''),
                       data.get('email',''), data.get('phone',''), data.get('current_cgpa'), data.get('target_cgpa',8.5), synthetic, now())).lastrowid
    return sid

def create_student_account(db, sid, roll, email='', password=None, is_demo=0):
    password = password or secrets.token_urlsafe(12)
    student_email = f"{roll.lower()}@student.nexora.local"
    # Email is internal for student accounts; login uses roll, not email.
    existing = db.execute('SELECT id FROM users WHERE student_id=?', (sid,)).fetchone()
    encoded = hash_password(password)
    if existing:
        db.execute('UPDATE users SET password=?,email=? WHERE id=?', (encoded, student_email, existing['id']))
        return existing['id'], password
    uid = db.execute('INSERT INTO users(email,name,password,role,student_id,institution,department,is_demo,settings,created_at) '
                     'SELECT ?,name,?,"student",id,?,?,?,"{}",? FROM students WHERE id=?',
                     (student_email, encoded, 'KITS, Singapur', 'Computer Science & Engineering', is_demo, now(), sid)).lastrowid
    return uid, password

def add_evidence(db, sid, data):
    return db.execute('INSERT INTO evidence(student_id,course,assessment_type,score,attendance,completion,topic,notes,recorded_on,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                      (sid, data['course'], data.get('assessment_type','Assessment'), data['score'], data['attendance'], data['completion'], data.get('topic', ''), data.get('notes', ''), data['recorded_on'], now())).lastrowid

def serialize_plan(db, row):
    p = dict(row)
    p['data'] = json.loads(p['data'])
    p['progress'] = [dict(r) for r in db.execute('SELECT * FROM progress WHERE plan_id=? ORDER BY recorded_on,id', (p['id'],))]
    return p

def add_notification(db, user_id, title, detail, type='info', entity_type=None, entity_id=None):
    db.execute('INSERT INTO notifications(user_id,title,detail,type,entity_type,entity_id,created_at) VALUES(?,?,?,?,?,?,?)',
               (user_id, title, detail, type, entity_type, entity_id, now()))

def visible_files_for_student(db, student):
    return [dict(r) for r in db.execute(
        '''SELECT * FROM academic_files WHERE
           audience='all' OR
           (audience='semester' AND semester=?) OR
           (audience='section' AND semester=? AND section=?) OR
           (audience='student' AND student_id=?)
           ORDER BY created_at DESC,id DESC''',
        (student['semester'], student['semester'], student['section'], student['id']))]

def student_snapshot(db, student_uid):
    user = db.execute('SELECT * FROM users WHERE id=? AND role="student"', (student_uid,)).fetchone()
    if not user or not user['student_id']:
        raise ValueError('Student account is not linked.')
    srow = db.execute('SELECT * FROM students WHERE id=?', (user['student_id'],)).fetchone()
    if not srow:
        raise ValueError('Student record not found.')
    student = dict(srow)
    student['evidence'] = [dict(r) for r in db.execute('SELECT * FROM evidence WHERE student_id=? ORDER BY recorded_on,id', (student['id'],))]
    student['risk'] = risk_for(student['evidence'])
    student['plans'] = [serialize_plan(db,r) for r in db.execute('SELECT * FROM plans WHERE student_id=? ORDER BY updated_at DESC,id DESC',(student['id'],))]
    student['reports'] = [dict(r) for r in db.execute('SELECT * FROM reports WHERE student_id=? ORDER BY created_at DESC,id DESC',(student['id'],))]
    student['files'] = visible_files_for_student(db, student)
    notifications = [dict(r) for r in db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50',(student_uid,))]
    return {'student': student, 'plans': student['plans'], 'reports': student['reports'], 'files': student['files'],
            'notifications': notifications, 'courses': COURSES, 'server_date': today(),
            'faculty_name': (db.execute('SELECT name FROM users WHERE id=?',(student['user_id'],)).fetchone() or {'name':'Faculty'})['name']}

def snapshot(db, uid):
    students = []
    for row in db.execute('SELECT * FROM students WHERE user_id=? ORDER BY name', (uid,)):
        s = dict(row)
        s['evidence'] = [dict(r) for r in db.execute('SELECT * FROM evidence WHERE student_id=? ORDER BY recorded_on,id', (s['id'],))]
        s['risk'] = risk_for(s['evidence'])
        students.append(s)
    plans = [serialize_plan(db, r) for r in db.execute('SELECT * FROM plans WHERE user_id=? ORDER BY updated_at DESC,id DESC', (uid,))]
    activity = [dict(r) for r in db.execute('SELECT * FROM activity WHERE user_id=? ORDER BY id DESC LIMIT 30', (uid,))]
    return {'students': students, 'plans': plans, 'activity': activity, 'courses': COURSES, 'server_date': today()}

def seed_workspace(db, uid):
    """All data below is fictional and labelled synthetic in API and UI."""
    if db.execute('SELECT 1 FROM students WHERE user_id=?', (uid,)).fetchone():
        return False
    names = ['Aarav Mehta', 'Diya Nair', 'Ishaan Kapoor', 'Kavya Iyer', 'Rohan Verma',
             'Sana Khan', 'Arjun Reddy', 'Meera Shah', 'Neel Patel', 'Tara Desai', 'Vivaan Joshi', 'Zoya Ali']
    scores = [32, 39, 44, 49, 56, 52, 62, 67, 72, 78, 85, 81]
    created = (date.today() - timedelta(days=21)).isoformat() + 'T09:00:00+00:00'
    for i, name in enumerate(names):
        sid = add_student(db, uid, {'name': name, 'roll': f'23CSE{101+i}', 'semester': 5 if i < 9 else 6,
                                   'section': 'A', 'email': f'23cse{101+i}@students.kitssingapur.ac.in',
                                   'current_cgpa': round(6.8 + i*0.16,2), 'target_cgpa': 8.5}, 1)
        create_student_account(db, sid, f'23CSE{101+i}', password='Nexora@1234', is_demo=1)
        selected = ['DSA', 'DBMS', 'OS'] if i < 9 else ['CN', 'SE', 'ML']
        base_rows = []
        for j, course in enumerate(selected):
            baseline = {'course': course, 'score': min(98, scores[i] + j*4), 'attendance': min(98, 53 + i*4 + j*2),
                        'completion': min(100, 38 + i*6 + j*3), 'topic': COURSES[course]['topics'][i % 3],
                        'notes': 'Synthetic demonstration record.', 'recorded_on': (date.today() - timedelta(days=28)).isoformat()}
            eid = add_evidence(db, sid, baseline)
            base_rows.append({**baseline, 'id': eid})
            if i >= 6:
                for week in [21, 14, 7, 0]:
                    diff = (28-week)//7
                    add_evidence(db, sid, {**baseline, 'score': min(100, baseline['score'] + diff),
                                         'attendance': min(100, baseline['attendance'] + diff),
                                         'recorded_on': (date.today()-timedelta(days=week)).isoformat()})
        if i < 6:
            course = selected[0 if i % 2 == 0 else 1]
            row = next(r for r in base_rows if r['course'] == course)
            plan = orchestrate(base_rows, course, 4, {'provider': 'rules'})
            plan['review_on'] = (date.today()+timedelta(days=[1, 2, 0, 3, 5, 7][i])).isoformat()
            status = 'Active' if i < 4 else 'Draft'
            for j, a in enumerate(plan['activities']):
                a['due_on'] = (date.today() + timedelta(days=(j-1)*3+i)).isoformat()
                a['completed'] = status == 'Active' and j < 2
                if a['completed']:
                    a['faculty_note'] = 'Sample activity completion recorded by faculty.'
            if status == 'Active':
                plan['trace'][-1] = {'agent': 'Review gate', 'status': 'complete', 'detail': 'Approved in the synthetic demo workspace.'}
            pid = db.execute('INSERT INTO plans(user_id,student_id,course,status,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                              (uid, sid, course, status, json.dumps(plan), created, now())).lastrowid
            if status == 'Active':
                for week, delta in [(14, 3), (7, 7), (0, 12 if i != 2 else 2)]:
                    followup = {**row, 'score': min(100, row['score']+delta), 'attendance': min(100, row['attendance']+max(0, delta//2)),
                                'completion': min(100, row['completion']+delta),
                                'recorded_on': (date.today()-timedelta(days=week)).isoformat()}
                    eid = add_evidence(db, sid, followup)
                    db.execute('INSERT INTO progress(plan_id,evidence_id,score,attendance,completion,notes,recorded_on,created_at) VALUES(?,?,?,?,?,?,?,?)',
                               (pid, eid, followup['score'], followup['attendance'], followup['completion'], 'Synthetic weekly check-in.', followup['recorded_on'], now()))
    log(db, uid, 'Sample workspace is ready', '12 fictional CSE students. No real academic data.', 'students', None)
    log(db, uid, 'Two drafts await your review', 'Approve a draft to activate its implementation checklist.', 'plans', None)
    log(db, uid, 'Weekly check-ins recorded', 'Open Progress to inspect evidence and recommendations.', 'progress', None)
    return True
