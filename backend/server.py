"""Same-origin local application server. Python 3.10+, standard library only.

For a departmental deployment, replace the development HTTP transport with a
hardened TLS reverse proxy/application server and perform a security review.
"""
from __future__ import annotations
import csv
import base64
from contextlib import closing
import hashlib
import io
import json
import logging
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from . import storage as store
from .domain import (DomainError, COURSES, number, text, today, valid_date,
                     validate_student, validate_evidence, orchestrate, evaluate_progress)

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'frontend' / 'dist'
SESSION_KEYS = {}  # Session-scoped credentials, never persisted or sent to the client.
RATE = defaultdict(list)
STATE_LOCK = threading.Lock()
PLAN_LOCKS = defaultdict(threading.Lock)
SESSION_HOURS = 12


def load_env():
    file = ROOT / '.env'
    if file.exists():
        for line in file.read_text('utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def rate_limit(key, limit, window=60):
    with STATE_LOCK:
        now = time.monotonic()
        RATE[key] = [t for t in RATE[key] if now - t < window]
        if len(RATE[key]) >= limit:
            raise DomainError('Too many requests. Please wait a minute and try again.', 429)
        RATE[key].append(now)
        if len(RATE) > 2000:
            for k in list(RATE):
                if not RATE[k] or now - RATE[k][-1] > window:
                    del RATE[k]


def validate_password(password):
    password = text(password, 'Password', 10, 128)
    if not re.search('[A-Za-z]', password) or not re.search('[0-9]', password):
        raise DomainError('Use at least 10 characters including a letter and a number.')
    return password


def validate_email(email):
    email = text(email, 'Email', 5, 150).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise DomainError('Enter a valid email address.')
    return email


class Handler(BaseHTTPRequestHandler):
    server_version = 'Nexora/1.0'
    sys_version = ''

    def log_message(self, fmt, *args):
        # Do not log bodies, keys, query strings, emails, or student evidence.
        logging.info('%s %s %s', self.command, urlparse(self.path).path, args[1] if len(args) > 1 else '')

    def headers_common(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")

    def send(self, data, status=200, cookies=None):
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.headers_common()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(raw)))
        if cookies:
            self.send_header('Set-Cookie', cookies)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def body(self):
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise DomainError('Send application/json.', 415)
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise DomainError('Invalid request length.')
        if size < 2 or size > 1_000_000:
            raise DomainError('Request must be valid JSON smaller than 1 MB.', 413)
        try:
            obj = json.loads(self.rfile.read(size), parse_constant=lambda x: (_ for _ in ()).throw(ValueError()))
            if not isinstance(obj, dict):
                raise ValueError()
            return obj
        except (ValueError, UnicodeError):
            raise DomainError('Request must be a JSON object.')

    def session(self, db, required=True):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
            token = ''
            for name in ('nexora_session', 'axiom_session'):
                if name in cookie:
                    token = cookie[name].value
                    break
        except Exception:
            token = ''
        hashed = hashlib.sha256(token.encode()).hexdigest()
        self.session_hash = hashed
        session = db.execute('SELECT * FROM sessions WHERE token_hash=? AND expires>?', (hashed, time.time())).fetchone()
        if not session:
            if required:
                raise DomainError('Please sign in to continue.', 401)
            return None, None
        user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
        return user, session

    def set_session(self, db, uid):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        hashed = hashlib.sha256(token.encode()).hexdigest()
        db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (hashed, uid, csrf, time.time()+SESSION_HOURS*3600))
        cookie = f'nexora_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_HOURS*3600}'
        if os.environ.get('COOKIE_SECURE') == 'true':
            cookie += '; Secure'
        return csrf, cookie

    def guard_origin(self):
        origin = self.headers.get('Origin')
        if origin and urlparse(origin).netloc != self.headers.get('Host'):
            raise DomainError('Cross-origin requests are not allowed.', 403)
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise DomainError('Cross-site requests are not allowed.', 403)
        if self.headers.get('X-Nexora-Request') != '1' and self.headers.get('X-Axiom-Request') != '1':
            raise DomainError('Missing request verification header.', 403)

    def own_student(self, db, uid, sid):
        row = db.execute('SELECT * FROM students WHERE id=? AND user_id=?', (sid, uid)).fetchone()
        if not row:
            raise DomainError('Student not found.', 404)
        return row

    def own_plan(self, db, uid, pid):
        row = db.execute('SELECT * FROM plans WHERE id=? AND user_id=?', (pid, uid)).fetchone()
        if not row:
            raise DomainError('Plan not found.', 404)
        return row, json.loads(row['data'])

    def key_for(self, user):
        with STATE_LOCK:
            key = SESSION_KEYS.get(self.session_hash, '')
        owner = os.environ.get('ENV_KEY_OWNER_EMAIL', '').lower().strip()
        if not key and not user['is_demo'] and user['email'].lower() == owner:
            key = os.environ.get('GEMINI_API_KEY', '')
        return key

    def require_faculty(self, user):
        if user['role'] != 'faculty':
            raise DomainError('This area is available only to faculty accounts.', 403)

    def own_student_for_student(self, db, user):
        if user['role'] != 'student' or not user['student_id']:
            raise DomainError('Student account is not linked to a student record.', 403)
        row = db.execute('SELECT * FROM students WHERE id=?', (user['student_id'],)).fetchone()
        if not row:
            raise DomainError('Your student record could not be found.', 404)
        return row

    def own_student_account(self, db, student_id):
        return db.execute('SELECT * FROM users WHERE role="student" AND student_id=?', (student_id,)).fetchone()

    def settings_for(self, user):
        prefs = {**store.defaults(), **json.loads(user['settings'])}
        with STATE_LOCK:
            source = 'Session memory' if SESSION_KEYS.get(self.session_hash) else 'Not configured'
        owner = os.environ.get('ENV_KEY_OWNER_EMAIL', '').lower().strip()
        if source == 'Not configured' and not user['is_demo'] and user['email'].lower() == owner and os.environ.get('GEMINI_API_KEY'):
            source = 'Server environment'
        return {**prefs, 'key_configured': source != 'Not configured', 'key_source': source}

    def do_GET(self):
        self.handle_request()

    def do_HEAD(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_PATCH(self):
        self.handle_request()

    def do_DELETE(self):
        self.handle_request()

    def handle_request(self):
        try:
            # Restrict Host for local-only mode; custom deployments must explicitly list hosts.
            host = self.headers.get('Host', '').split(':')[0]
            allowed = os.environ.get('NEXORA_ALLOWED_HOSTS', os.environ.get('AXIOM_ALLOWED_HOSTS', 'localhost,127.0.0.1')).split(',')
            if host not in [h.strip() for h in allowed]:
                raise DomainError('Host is not allowed by this local application.', 400)
            path = urlparse(self.path).path.rstrip('/') or '/'
            if path.startswith('/api/'):
                if self.command not in ('GET', 'HEAD'):
                    self.guard_origin()
                with closing(store.connect()) as db, db:
                    self.api(db, path)
            elif self.command in ('GET', 'HEAD'):
                self.static(path)
            else:
                raise DomainError('Route not found.', 404)
        except DomainError as e:
            self.send({'error': e.message}, e.status)
        except sqlite3.IntegrityError:
            self.send({'error': 'This email or roll number already exists in this workspace.'}, 409)
        except sqlite3.OperationalError:
            self.send({'error': 'The database is busy. Retry in a moment.'}, 503)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            logging.exception('Unexpected application error (request payload not logged)')
            self.send({'error': 'An unexpected error occurred. Check the local server log.'}, 500)

    def api(self, db, path):
        method = 'GET' if self.command == 'HEAD' else self.command
        if path == '/api/health' and method == 'GET':
            return self.send({'status': 'ok', 'version': '1.0.0'})
        if path == '/api/session' and method == 'GET':
            user, sess = self.session(db, False)
            return self.send({'user': store.public_user(user) if user else None, 'csrf': sess['csrf'] if sess else None})
        if path in ['/api/auth/signup', '/api/auth/login', '/api/auth/demo', '/api/auth/student-login'] and method == 'POST':
            rate_limit(('auth', self.client_address[0]), 20)
            data = self.body()
            if path.endswith('/student-login'):
                roll = text(data.get('roll'), 'Roll number', 2, 32).upper()
                password = text(data.get('password'), 'Password', 1, 128)
                account = db.execute('SELECT u.*,s.roll FROM users u JOIN students s ON s.id=u.student_id WHERE u.role="student" AND s.roll=? AND s.user_id IS NOT NULL', (roll,)).fetchone()
                encoded = account['password'] if account else 'pbkdf2_sha256$600000$00000000000000000000000000000000$' + '0'*64
                if not account or not store.check_password(password, encoded):
                    raise DomainError('Roll number or password is incorrect.', 401)
                uid = account['id']
            elif path.endswith('/signup'):
                name = text(data.get('name'), 'Name', 2, 80)
                email = validate_email(data.get('email'))
                password = validate_password(data.get('password'))
                institution = text(data.get('institution', 'KITS, Singapur'), 'Institution', 2, 140)
                uid = db.execute('INSERT INTO users(email,name,password,role,institution,settings,created_at) VALUES(?,?,?,?,?,?,?)',
                                 (email, name, store.hash_password(password), 'faculty', institution, json.dumps(store.defaults()), store.now())).lastrowid
                store.log(db, uid, 'Workspace created', 'Add your first student or load a synthetic sample cohort.')
            elif path.endswith('/demo'):
                uid = db.execute('INSERT INTO users(email,name,password,role,institution,is_demo,settings,created_at) VALUES(?,?,?,?,?,?,?,?)',
                                 (f'demo-{secrets.token_hex(10)}@example.invalid', 'Dr. Ananya Rao', store.hash_password(secrets.token_urlsafe(32)), 'faculty',
                                  'KITS, Singapur', 1, json.dumps({'provider': 'rules', 'model': 'gemini-2.5-flash', 'consent': False}), store.now())).lastrowid
                store.seed_workspace(db, uid)
            else:
                email = validate_email(data.get('email'))
                password = text(data.get('password'), 'Password', 1, 128)
                user = db.execute('SELECT * FROM users WHERE email=? AND is_demo=0', (email,)).fetchone()
                # Constant-cost work even for unknown email addresses.
                encoded = user['password'] if user else 'pbkdf2_sha256$600000$00000000000000000000000000000000$' + '0'*64
                if not store.check_password(password, encoded) or not user:
                    raise DomainError('Email or password is incorrect.', 401)
                uid = user['id']
            csrf, cookie = self.set_session(db, uid)
            user = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
            db.commit()
            return self.send({'user': store.public_user(user), 'csrf': csrf}, 201 if path.endswith('/signup') or path.endswith('/demo') else 200, cookie)
        user, sess = self.session(db)
        uid = user['id']
        if method not in ('GET', 'HEAD'):
            if not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), sess['csrf']):
                raise DomainError('Your session verification expired. Refresh the page and try again.', 403)
            data = self.body()
        if path == '/api/auth/logout' and method == 'POST':
            db.execute('DELETE FROM sessions WHERE token_hash=?', (self.session_hash,))
            with STATE_LOCK:
                SESSION_KEYS.pop(self.session_hash, None)
            db.commit()
            return self.send({'ok': True}, cookies='nexora_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
        if path == '/api/auth/password' and method == 'POST':
            if user['is_demo']:
                raise DomainError('Create a personal account to manage your password.')
            rate_limit(('password', uid), 5)
            if not store.check_password(text(data.get('current_password'), 'Current password', 1, 128), user['password']):
                raise DomainError('Current password is incorrect.', 400)
            new = validate_password(data.get('new_password'))
            if store.check_password(new, user['password']):
                raise DomainError('Choose a different new password.')
            db.execute('UPDATE users SET password=? WHERE id=?', (store.hash_password(new), uid))
            old_tokens = [r['token_hash'] for r in db.execute('SELECT token_hash FROM sessions WHERE user_id=?', (uid,))]
            db.execute('DELETE FROM sessions WHERE user_id=?', (uid,))
            with STATE_LOCK:
                for token in old_tokens:
                    SESSION_KEYS.pop(token, None)
            csrf, cookie = self.set_session(db, uid)
            store.log(db, uid, 'Password updated', 'Other sessions were signed out.')
            db.commit()
            return self.send({'ok': True, 'csrf': csrf}, cookies=cookie)
        if path == '/api/notifications' and method == 'GET':
            return self.send({'notifications':[dict(r) for r in db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50',(uid,))]})
        m = re.fullmatch(r'/api/notifications/(\d+)', path)
        if m and method == 'PATCH':
            db.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?',(store.now(),int(m[1]),uid)); db.commit()
            return self.send({'ok':True})
        if path == '/api/profile' and method == 'PATCH':
            name = text(data.get('name'), 'Name', 2, 80)
            institution = text(data.get('institution'), 'Institution', 2, 140)
            department = text(data.get('department'), 'Department', 2, 120)
            bio = text(data.get('bio', ''), 'Bio', 0, 500)
            db.execute('UPDATE users SET name=?,institution=?,department=?,bio=? WHERE id=?', (name, institution, department, bio, uid))
            store.log(db, uid, 'Profile updated')
            db.commit()
            return self.send({'user': store.public_user(db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone())})
        if path == '/api/student/target' and method == 'PATCH':
            if user['role'] != 'student':
                raise DomainError('Student target settings are available only to student accounts.', 403)
            student = self.own_student_for_student(db, user)
            target = number(data.get('target_cgpa'), 'Target CGPA', 0, 10)
            db.execute('UPDATE students SET target_cgpa=? WHERE id=?', (target, student['id']))
            store.add_notification(db, user['id'], 'Target CGPA updated', f'Your target is now {target:g}.')
            db.commit()
            return self.send({'ok': True, 'target_cgpa': target})

        if path == '/api/student/tasks' and method == 'PATCH':
            if user['role'] != 'student':
                raise DomainError('This task action is available only to students.', 403)
            student = self.own_student_for_student(db, user)
            try:
                pid, idx = int(data.get('plan_id')), int(data.get('index'))
            except (TypeError, ValueError):
                raise DomainError('Choose a valid task.')
            row = db.execute('SELECT * FROM plans WHERE id=? AND student_id=? AND status="Active"', (pid, student['id'])).fetchone()
            if not row:
                raise DomainError('That study plan is not active or does not belong to you.', 404)
            plan = json.loads(row['data'])
            if not 0 <= idx < len(plan['activities']):
                raise DomainError('That task could not be found.')
            completed = data.get('completed')
            if not isinstance(completed, bool):
                raise DomainError('Choose whether the task is done.')
            a = plan['activities'][idx]
            a['completed'] = completed
            a['difficulty'] = data.get('difficulty') if data.get('difficulty') in ['Easy','Normal','Difficult'] else a.get('difficulty','')
            a['completed_by'] = 'student' if completed else None
            a['completed_at'] = store.now() if completed else None
            db.execute('UPDATE plans SET data=?,updated_at=? WHERE id=?', (json.dumps(plan), store.now(), pid))
            faculty_id = row['user_id']
            store.add_notification(db, faculty_id, f'{student["name"]} updated a task', a['title'], 'progress', 'plan', pid)
            db.commit()
            return self.send({'ok': True})

        if path == '/api/student/notifications' and method == 'GET':
            if user['role'] != 'student':
                raise DomainError('Student notifications are available only to student accounts.', 403)
            return self.send({'notifications':[dict(r) for r in db.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 50',(uid,))]})

        m = re.fullmatch(r'/api/student/notifications/(\d+)', path)
        if m and method == 'PATCH':
            if user['role'] != 'student':
                raise DomainError('Student notifications are available only to student accounts.', 403)
            db.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?', (store.now(), int(m[1]), uid))
            db.commit()
            return self.send({'ok': True})

        if path == '/api/files' and method == 'GET':
            if user['role'] == 'student':
                student = self.own_student_for_student(db, user)
                return self.send({'files': store.visible_files_for_student(db, student)})
            self.require_faculty(user)
            return self.send({'files':[dict(r) for r in db.execute('SELECT * FROM academic_files WHERE user_id=? ORDER BY created_at DESC,id DESC',(uid,))]})

        if path == '/api/files' and method == 'POST':
            self.require_faculty(user)
            name = text(data.get('file_name'),'File name',1,180)
            category = text(data.get('category','Other'),'Category',2,40)
            allowed_mimes = {'application/pdf','text/csv','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             'application/vnd.ms-excel','application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                             'application/msword','text/plain','image/png','image/jpeg'}
            mime = text(data.get('mime_type','application/octet-stream'),'File type',3,120)
            if mime not in allowed_mimes:
                raise DomainError('This file type is not supported.')
            try:
                raw = base64.b64decode(text(data.get('content_b64'),'File content',1,8_000_000), validate=True)
            except (ValueError, TypeError):
                raise DomainError('The file could not be read.')
            if not raw or len(raw)>5_000_000:
                raise DomainError('Choose a file smaller than 5 MB.')
            ext = Path(name).suffix.lower()
            safe = secrets.token_hex(16)+ext
            root = store.ROOT / 'data' / 'uploads'; root.mkdir(parents=True, exist_ok=True)
            path_on_disk = root / safe
            path_on_disk.write_bytes(raw)
            audience = data.get('audience','all')
            if audience not in ['all','semester','section','student']:
                raise DomainError('Choose who can access this file.')
            sem = int(data['semester']) if audience in ['semester','section'] and data.get('semester') else None
            section = text(data.get('section'),'Section',1,8) if audience=='section' and data.get('section') else None
            sid = int(data['student_id']) if audience=='student' and data.get('student_id') else None
            if audience=='student':
                self.own_student(db, uid, sid)
            fid = db.execute('INSERT INTO academic_files(user_id,file_name,category,mime_type,size_bytes,storage_path,audience,semester,section,student_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                             (uid,name,category,mime,len(raw),str(path_on_disk.relative_to(store.ROOT)),audience,sem,section,sid,store.now())).lastrowid
            recipients = []
            if audience=='all':
                recipients = [r['id'] for r in db.execute('SELECT id FROM users WHERE role="student" AND student_id IN (SELECT id FROM students WHERE user_id=?)',(uid,))]
            elif audience=='semester':
                recipients = [r['id'] for r in db.execute('SELECT u.id FROM users u JOIN students s ON s.id=u.student_id WHERE u.role="student" AND s.user_id=? AND s.semester=?',(uid,sem))]
            elif audience=='section':
                recipients = [r['id'] for r in db.execute('SELECT u.id FROM users u JOIN students s ON s.id=u.student_id WHERE u.role="student" AND s.user_id=? AND s.semester=? AND s.section=?',(uid,sem,section))]
            elif audience=='student':
                acct=self.own_student_account(db,sid); recipients=[acct['id']] if acct else []
            for rid in recipients:
                store.add_notification(db,rid,'New academic file',f'{name} is available in Academic Files.','file','file',fid)
            store.log(db, uid, 'Academic file uploaded', f'{name} · {category}', 'file', fid)
            db.commit()
            return self.send({'id':fid},201)

        m = re.fullmatch(r'/api/files/(\d+)$', path)
        if m and method == 'DELETE':
            self.require_faculty(user); fid=int(m[1])
            row=db.execute('SELECT * FROM academic_files WHERE id=? AND user_id=?',(fid,uid)).fetchone()
            if not row: raise DomainError('File not found.',404)
            disk=store.ROOT / row['storage_path']
            try:
                if disk.exists(): disk.unlink()
            except OSError:
                raise DomainError('The file could not be removed from local storage.',409)
            db.execute('DELETE FROM academic_files WHERE id=?',(fid,)); store.log(db,uid,'Academic file deleted',row['file_name'],'file',fid); db.commit()
            return self.send({'ok':True})
        m = re.fullmatch(r'/api/files/(\d+)/download', path)
        if m and method == 'GET':
            fid=int(m[1]); row=db.execute('SELECT * FROM academic_files WHERE id=?',(fid,)).fetchone()
            if not row: raise DomainError('File not found.',404)
            if user['role']=='faculty':
                if row['user_id']!=uid: raise DomainError('File not found.',404)
            else:
                student=self.own_student_for_student(db,user)
                if not any(f['id']==fid for f in store.visible_files_for_student(db,student)):
                    raise DomainError('File not found.',404)
            disk=store.ROOT / row['storage_path']
            if not disk.exists(): raise DomainError('This file is no longer available.',410)
            raw=disk.read_bytes()
            self.send_response(200); self.headers_common()
            self.send_header('Content-Type',row['mime_type'])
            self.send_header('Content-Disposition',f"attachment; filename*=UTF-8''{row['file_name']}")
            self.send_header('Content-Length',str(len(raw))); self.end_headers()
            if self.command!='HEAD': self.wfile.write(raw)
            return

        if path == '/api/reports' and method == 'GET':
            if user['role']=='faculty':
                rows=[dict(r) for r in db.execute('SELECT r.*,s.name AS student_name,s.roll FROM reports r JOIN students s ON s.id=r.student_id WHERE r.user_id=? ORDER BY r.created_at DESC,r.id DESC',(uid,))]
                return self.send({'reports':rows})
            student=self.own_student_for_student(db,user)
            rows=[dict(r) for r in db.execute('SELECT * FROM reports WHERE student_id=? AND shared=1 ORDER BY created_at DESC,id DESC',(student['id'],))]
            return self.send({'reports':rows})

        if path == '/api/reports' and method == 'POST':
            self.require_faculty(user)
            sid=int(data.get('student_id')); self.own_student(db,uid,sid)
            plan_id=int(data.get('plan_id')) if data.get('plan_id') else None
            plan_row, plan_data = self.own_plan(db,uid,plan_id) if plan_id else (None,None)
            s=self.own_student(db,uid,sid)
            evidence=[dict(r) for r in db.execute('SELECT * FROM evidence WHERE student_id=? ORDER BY recorded_on,id',(sid,))]
            risk=__import__('backend.domain',fromlist=['risk_for']).risk_for(evidence)
            title=f'{s["name"]} · Academic Report'
            payload={'student':{k:s[k] for k in ['name','roll','reg_no','semester','section','email','current_cgpa','target_cgpa']},
                     'risk':risk,'evidence':evidence,'plan':plan_data,'generated_on':store.now()}
            rid=db.execute('INSERT INTO reports(user_id,student_id,title,data,created_at) VALUES(?,?,?,?,?)',(uid,sid,title,json.dumps(payload),store.now())).lastrowid
            store.log(db,uid,'Academic report generated',title,'report',rid)
            db.commit()
            return self.send({'id':rid,'report':payload},201)

        m=re.fullmatch(r'/api/reports/(\d+)/share',path)
        if m and method=='POST':
            self.require_faculty(user); rid=int(m[1]); row=db.execute('SELECT * FROM reports WHERE id=? AND user_id=?',(rid,uid)).fetchone()
            if not row: raise DomainError('Report not found.',404)
            acct=self.own_student_account(db,row['student_id'])
            if not acct: raise DomainError('This student does not have a portal account yet.')
            db.execute('UPDATE reports SET shared=1,shared_at=? WHERE id=?',(store.now(),rid))
            store.add_notification(db,acct['id'],'New Academic Report','Your faculty has shared a new performance report.','report','report',rid)
            db.commit()
            return self.send({'ok':True})

        m=re.fullmatch(r'/api/reports/(\d+)$',path)
        if m and method=='GET':
            rid=int(m[1]); row=db.execute('SELECT * FROM reports WHERE id=?',(rid,)).fetchone()
            if not row: raise DomainError('Report not found.',404)
            if user['role']=='faculty' and row['user_id']!=uid: raise DomainError('Report not found.',404)
            if user['role']=='student':
                if row['student_id']!=user['student_id'] or not row['shared']: raise DomainError('Report not found.',404)
            p=dict(row); p['data']=json.loads(p['data'])
            return self.send(p)

        if path == '/api/workspace' and method == 'GET':
            if user['role'] == 'student':
                return self.send(store.student_snapshot(db, uid))
            return self.send(store.snapshot(db, uid))
        if path == '/api/workspace/seed' and method == 'POST':
            self.require_faculty(user)
            if not store.seed_workspace(db, uid):
                raise DomainError('Sample data can only be loaded into an empty workspace.', 409)
            db.commit()
            return self.send({'ok': True})
        if path == '/api/settings' and method == 'GET':
            self.require_faculty(user)
            return self.send(self.settings_for(user))
        if path == '/api/settings' and method == 'PATCH':
            self.require_faculty(user)
            provider = data.get('provider', 'rules')
            if provider not in ['rules', 'gemini', 'ollama']:
                raise DomainError('Choose Local rules, Gemini, or Ollama.')
            model = text(data.get('model', 'gemini-2.5-flash'), 'Model', 1, 100)
            if provider == 'gemini' and not re.fullmatch('[a-zA-Z0-9._-]+', model):
                raise DomainError('Enter a valid Gemini model ID.')
            if provider == 'ollama' and ('cloud' in model.lower() or not re.fullmatch('[a-zA-Z0-9._:/-]+', model)):
                raise DomainError('Choose a local Ollama model, not a cloud model.')
            if not isinstance(data.get('consent', False), bool):
                raise DomainError('Consent must be true or false.')
            prefs = {'provider': provider, 'model': model, 'consent': data.get('consent', False)}
            db.execute('UPDATE users SET settings=? WHERE id=?', (json.dumps(prefs), uid))
            if 'api_key' in data and data['api_key']:
                key = text(data['api_key'], 'API key', 10, 300)
                with STATE_LOCK:
                    SESSION_KEYS[self.session_hash] = key
            if data.get('clear_key'):
                with STATE_LOCK:
                    SESSION_KEYS.pop(self.session_hash, None)
            store.log(db, uid, 'AI settings updated', f'Provider: {provider}. Credentials are not stored in the database.')
            db.commit()
            return self.send(self.settings_for(db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()))
        if path == '/api/settings/test' and method == 'POST':
            self.require_faculty(user)
            rate_limit(('provider-test', uid), 4)
            synthetic = {'id': 0, 'course': 'DSA', 'score': 45, 'attendance': 70, 'completion': 55,
                         'topic': 'Recursion', 'notes': '', 'recorded_on': today()}
            draft = orchestrate([synthetic], 'DSA', 2, self.settings_for(user), self.key_for(user))
            return self.send({'ok': True, 'message': draft['source'] + ' passed a structured planning test using fictional evidence. No student record was transmitted or saved.'})
        if path == '/api/students' and method == 'GET':
            self.require_faculty(user)
            rows=[dict(r) for r in db.execute('SELECT * FROM students WHERE user_id=? ORDER BY name COLLATE NOCASE, id',(uid,))]
            return self.send({'students':rows})
        if path == '/api/students' and method == 'POST':
            self.require_faculty(user)
            s = validate_student(data)
            sid = store.add_student(db, uid, s)
            temp_password = validate_password(data.get('portal_password') or 'Nexora@1234')
            store.create_student_account(db, sid, s['roll'], s.get('email',''), temp_password)
            store.log(db, uid, 'Student added', s['name'], 'student', sid)
            db.commit()
            return self.send({'id': sid, 'temporary_password': temp_password}, 201)
        if path == '/api/students/import' and method == 'POST':
            self.require_faculty(user)
            raw = text(data.get('csv'), 'CSV', 1, 500_000)
            try:
                reader = csv.DictReader(io.StringIO(raw.lstrip('\ufeff')))
                required = {'name', 'roll', 'semester', 'section', 'course', 'score', 'attendance', 'completion'}
                if not required.issubset(set(reader.fieldnames or [])):
                    raise DomainError('CSV needs columns: ' + ', '.join(sorted(required)) + '.')
                rows = list(reader)
            except csv.Error:
                raise DomainError('Invalid CSV format.')
            if not 1 <= len(rows) <= 500:
                raise DomainError('Import 1–500 evidence rows at a time.')
            validated = []
            profiles = {}
            existing = {r['roll']: dict(r) for r in db.execute('SELECT * FROM students WHERE user_id=?', (uid,))}
            seen_evidence = set()
            for idx, row in enumerate(rows, 2):
                try:
                    s = validate_student({**row, 'email': row.get('email') or ''})
                    ev = validate_evidence({**row, 'recorded_on': row.get('recorded_on') or today(), 'topic': row.get('topic') or '', 'notes': row.get('notes') or ''})
                    prior = profiles.get(s['roll']) or existing.get(s['roll'])
                    if prior and any(prior[k] != s[k] for k in ['name', 'semester', 'section']):
                        raise DomainError('The same roll number has conflicting student details.')
                    key = (s['roll'], ev['course'], ev['recorded_on'])
                    if key in seen_evidence:
                        raise DomainError('Duplicate roll / course / date in this CSV.')
                    if s['roll'] in existing and db.execute('SELECT 1 FROM evidence WHERE student_id=? AND course=? AND recorded_on=?',
                                                           (existing[s['roll']]['id'], ev['course'], ev['recorded_on'])).fetchone():
                        raise DomainError('Evidence already exists for this roll / course / date.')
                    seen_evidence.add(key)
                    profiles[s['roll']] = s
                    validated.append((s, ev))
                except DomainError as e:
                    raise DomainError(f'Row {idx}: {e.message} Nothing was imported.')
            created = 0
            for s, ev in validated:
                if s['roll'] not in existing:
                    sid = store.add_student(db, uid, s)
                    store.create_student_account(db, sid, s['roll'], s.get('email',''), 'Nexora@1234')
                    existing[s['roll']] = {**s, 'id': sid}
                    created += 1
                store.add_evidence(db, existing[s['roll']]['id'], ev)
            store.log(db, uid, 'Evidence imported', f'{created} new students, {len(validated)} evidence records.', 'students')
            db.commit()
            return self.send({'students_created': created, 'evidence_created': len(validated)})
        m = re.fullmatch(r'/api/students/(\d+)', path)
        if m:
            self.require_faculty(user)
            sid = int(m[1])
            self.own_student(db, uid, sid)
            if method == 'PATCH':
                s = validate_student(data)
                db.execute('UPDATE students SET name=?,roll=?,semester=?,section=?,reg_no=?,email=?,phone=?,current_cgpa=?,target_cgpa=? WHERE id=?',
                           (s['name'], s['roll'], s['semester'], s['section'], s['reg_no'], s['email'], s['phone'],
                            s['current_cgpa'], s['target_cgpa'], sid))
                store.log(db, uid, 'Student details updated', s['name'], 'student', sid)
                db.commit()
                return self.send({'ok': True})
            if method == 'DELETE':
                if data.get('confirm') != 'DELETE':
                    raise DomainError('Type DELETE to confirm removal.')
                db.execute('DELETE FROM students WHERE id=?', (sid,))
                store.log(db, uid, 'Student record deleted', 'Associated evidence, plans and progress were removed.')
                db.commit()
                return self.send({'ok': True})
        m = re.fullmatch(r'/api/students/(\d+)/reset-password', path)
        if m and method == 'POST':
            self.require_faculty(user)
            sid=int(m[1]); student=self.own_student(db,uid,sid)
            new=validate_password(data.get('new_password'))
            acct=self.own_student_account(db,sid)
            if not acct:
                _, _ = store.create_student_account(db,sid,student['roll'],student['email'],new)
            else:
                db.execute('UPDATE users SET password=? WHERE id=?',(store.hash_password(new),acct['id']))
                db.execute('DELETE FROM sessions WHERE user_id=?',(acct['id'],))
            store.log(db,uid,'Student portal password reset',f'{student["name"]} · password replaced; current password not exposed.','student',sid)
            db.commit()
            return self.send({'ok':True})
        m = re.fullmatch(r'/api/students/(\d+)/evidence', path)
        if m and method == 'POST':
            self.require_faculty(user)
            sid = int(m[1])
            self.own_student(db, uid, sid)
            ev = validate_evidence(data)
            eid = store.add_evidence(db, sid, ev)
            store.log(db, uid, 'Performance evidence added', ev['course'], 'student', sid)
            db.commit()
            return self.send({'id': eid}, 201)
        if path == '/api/plans/generate' and method == 'POST':
            self.require_faculty(user)
            rate_limit(('generate', uid), 12)
            try:
                sid = int(data.get('student_id'))
            except (ValueError, TypeError):
                raise DomainError('Choose a student.')
            self.own_student(db, uid, sid)
            course = data.get('course')
            if course not in COURSES:
                raise DomainError('Choose a CSE course.')
            weeks = number(data.get('weeks', 4), 'Duration in weeks', 1, 8)
            if not weeks.is_integer():
                raise DomainError('Duration must be a whole number of weeks.')
            records = [dict(r) for r in db.execute('SELECT * FROM evidence WHERE student_id=?', (sid,))]
            parent_id = data.get('parent_id')
            revision, adjustment = 1, None
            if parent_id:
                old, old_data = self.own_plan(db, uid, parent_id)
                if old['student_id'] != sid or old['course'] != course or old['status'] != 'Active':
                    raise DomainError('Only an active plan for this student and course can be revised.')
                if db.execute("SELECT 1 FROM plans WHERE parent_id=? AND status='Draft'", (parent_id,)).fetchone():
                    raise DomainError('A revision draft already exists. Review it before generating another.', 409)
                progress = [dict(r) for r in db.execute('SELECT * FROM progress WHERE plan_id=?', (parent_id,))]
                adjustment = evaluate_progress(old_data['baseline'], progress)
                if not progress:
                    raise DomainError('Record follow-up evidence before recommending a revision.')
                revision = old['revision'] + 1
            prefs = self.settings_for(user)
            lock = PLAN_LOCKS[uid]
            if not lock.acquire(blocking=False):
                raise DomainError('A plan is already being generated in this workspace. Please wait.', 409)
            try:
                plan = orchestrate(records, course, int(weeks), prefs, self.key_for(user), adjustment)
                if adjustment:
                    plan['adjustment'] = adjustment
                pid = db.execute('INSERT INTO plans(user_id,student_id,course,status,revision,parent_id,data,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                 (uid, sid, course, 'Draft', revision, parent_id, json.dumps(plan), store.now(), store.now())).lastrowid
                store.log(db, uid, 'Study Plan draft created', f'{course} · {plan["source"]} · Faculty approval required', 'plan', pid)
                db.commit()
            finally:
                lock.release()
            return self.send({'id': pid, 'plan': plan}, 201)
        m = re.fullmatch(r'/api/plans/(\d+)', path)
        if m and method == 'PATCH':
            self.require_faculty(user)
            pid = int(m[1])
            # Serialize state transitions and read-modify-write task changes.
            db.execute('BEGIN IMMEDIATE')
            row, plan = self.own_plan(db, uid, pid)
            action = data.get('action')
            status = row['status']
            if action == 'approve':
                if status != 'Draft':
                    raise DomainError('Only a draft can be approved.', 409)
                # Prevent concurrent active study plans for the same student/course.
                db.execute("UPDATE plans SET status='Archived',updated_at=? WHERE user_id=? AND student_id=? AND course=? AND status='Active'",
                           (store.now(), uid, row['student_id'], row['course']))
                status = 'Active'
                plan['approved_at'] = store.now()
                plan['approved_by'] = user['name']
                plan['trace'][-1] = {'agent': 'Review gate', 'status': 'complete', 'detail': 'Approved by faculty. Checklist is now ready for implementation.'}
            elif action == 'complete':
                if status != 'Active' or not all(a['completed'] for a in plan['activities']):
                    raise DomainError('Complete every activity in an active plan before closing it.')
                status = 'Completed'
            elif action == 'archive':
                if status == 'Archived':
                    raise DomainError('This plan is already archived.', 409)
                status = 'Archived'
            elif action == 'task':
                if status != 'Active':
                    raise DomainError('Approve this draft before recording implementation.', 409)
                idx = number(data.get('index'), 'Activity index', 0, len(plan['activities'])-1)
                if not idx.is_integer() or not isinstance(data.get('completed'), bool):
                    raise DomainError('Choose a valid task and completion state.')
                a = plan['activities'][int(idx)]
                a['completed'] = data['completed']
                a['faculty_note'] = text(data.get('faculty_note', a.get('faculty_note', '')), 'Completion note', 0, 600)
                a['completed_at'] = store.now() if a['completed'] else None
            elif action == 'edit':
                if status != 'Draft':
                    raise DomainError('Only draft plans can be edited.', 409)
                plan['title'] = text(data.get('title', plan['title']), 'Title', 4, 160)
                plan['objective'] = text(data.get('objective', plan['objective']), 'Objective', 4, 700)
                plan['target_score'] = number(data.get('target_score', plan['target_score']), 'Target score')
                plan['review_on'] = valid_date(data.get('review_on', plan['review_on']), 'Review date')
                changes = data.get('activities')
                if changes is not None:
                    if not isinstance(changes, list) or len(changes) != len(plan['activities']):
                        raise DomainError('Preserve all activities when editing a draft.')
                    for a, b in zip(plan['activities'], changes):
                        a['title'] = text(b.get('title'), 'Activity title', 3, 160)
                        a['description'] = text(b.get('description'), 'Activity details', 8, 900)
                        a['due_on'] = valid_date(b.get('due_on'), 'Activity due date')
                plan['faculty_edited'] = True
            else:
                raise DomainError('Unknown plan action.')
            db.execute('UPDATE plans SET status=?,data=?,updated_at=? WHERE id=?', (status, json.dumps(plan), store.now(), pid))
            store.log(db, uid, {'approve': 'Plan approved', 'complete': 'Plan completed', 'archive': 'Plan archived', 'task': 'Implementation updated', 'edit': 'Draft edited'}[action],
                      plan['title'], 'plan', pid)
            db.commit()
            return self.send({'ok': True})
        m = re.fullmatch(r'/api/plans/(\d+)/progress', path)
        if m and method == 'POST':
            self.require_faculty(user)
            pid = int(m[1])
            db.execute('BEGIN IMMEDIATE')
            row, plan = self.own_plan(db, uid, pid)
            if row['status'] != 'Active':
                raise DomainError('Progress can only be logged against an active plan.')
            ev = validate_evidence({**data, 'course': row['course'], 'topic': plan['baseline'].get('topic', '')})
            latest = db.execute('SELECT MAX(recorded_on) AS d FROM progress WHERE plan_id=?', (pid,)).fetchone()['d']
            if ev['recorded_on'] < (latest or plan['baseline']['recorded_on']):
                raise DomainError('Follow-up date must not precede the baseline or the latest check-in.')
            eid = store.add_evidence(db, row['student_id'], ev)
            db.execute('INSERT INTO progress(plan_id,evidence_id,score,attendance,completion,notes,recorded_on,created_at) VALUES(?,?,?,?,?,?,?,?)',
                       (pid, eid, ev['score'], ev['attendance'], ev['completion'], ev['notes'], ev['recorded_on'], store.now()))
            store.log(db, uid, 'Progress check-in recorded', f"{row['course']} · assessment {ev['score']:g}%", 'plan', pid)
            db.commit()
            return self.send({'ok': True}, 201)
        raise DomainError('API route not found.', 404)

    def static(self, path):
        decoded = unquote(path)
        candidate = (DIST / decoded.lstrip('/')).resolve()
        if DIST.resolve() not in candidate.parents and candidate != DIST.resolve():
            raise DomainError('File not found.', 404)
        if not candidate.is_file():
            if Path(decoded).suffix:
                raise DomainError('File not found.', 404)
            candidate = DIST / 'index.html'
        if not candidate.exists():
            raise DomainError('Frontend build is missing. Run npm install, then npm run build.', 503)
        raw = candidate.read_bytes()
        self.send_response(200)
        self.headers_common()
        mime = mimetypes.guess_type(str(candidate))[0] or 'application/octet-stream'
        self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') or mime in ['application/javascript', 'image/svg+xml'] else ''))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)


def main():
    load_env()
    store.init_db()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    host = os.environ.get('NEXORA_HOST', os.environ.get('AXIOM_HOST', '127.0.0.1'))
    port = int(os.environ.get('NEXORA_PORT', os.environ.get('AXIOM_PORT', '8000')))
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    print(f'\n  NEXORA / Academic Intelligence Platform\n  Open http://localhost:{port}\n  Developed by Batch - 8 of CSE-A\n  Local development server. Press Ctrl+C to stop.\n', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nNexora stopped.')
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
