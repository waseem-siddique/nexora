import sys,getpass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.server import load_env,validate_password
from backend import storage as s
load_env();s.init_db()
email=input('Account email: ').strip().lower()
with s.connect() as db:
 user=db.execute('SELECT * FROM users WHERE email=? AND is_demo=0',(email,)).fetchone()
 if not user: raise SystemExit('No local personal account matches that email.')
 password=validate_password(getpass.getpass('New password (10+ characters, letter and number): '))
 if password!=getpass.getpass('Confirm new password: '):raise SystemExit('Passwords do not match. No changes made.')
 db.execute('UPDATE users SET password=? WHERE id=?',(s.hash_password(password),user['id']))
 db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
print('Password reset. All account sessions revoked. Restart the server to clear any old in-memory provider keys.')
