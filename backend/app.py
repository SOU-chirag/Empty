import os
import sys
from datetime import datetime, date
from functools import wraps

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_conn, init_db

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
)

# Attempt auto database initialization on startup
try:
    init_db()
except Exception as _e:
    print(f"[SkillSwap] Note: Database auto-init skipped or waiting for credentials: {_e}")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'frontend')

AVAILABILITY_LABELS = ['Weekdays', 'Weekends', 'Mornings', 'Afternoons', 'Evenings', 'Custom']


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────
def iso(dt):
    if dt is None:
        return None
    if isinstance(dt, (datetime, date)):
        return dt.isoformat()
    return str(dt)


def current_user_row(cur):
    uid = session.get('user_id')
    if not uid:
        return None
    cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
    return cur.fetchone()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get('user_id'):
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*a, **kw)
    return wrapper


def serialize_user(cur, row):
    uid = row['user_id']
    cur.execute("""SELECT s.skill_name FROM user_skills us JOIN skills s ON s.skill_id=us.skill_id
                   WHERE us.user_id=%s AND us.skill_type='offer'""", (uid,))
    offer = [r['skill_name'] for r in cur.fetchall()]
    cur.execute("""SELECT s.skill_name FROM user_skills us JOIN skills s ON s.skill_id=us.skill_id
                   WHERE us.user_id=%s AND us.skill_type='want'""", (uid,))
    want = [r['skill_name'] for r in cur.fetchall()]
    cur.execute("""SELECT ao.label FROM user_availability ua JOIN availability_options ao
                   ON ao.availability_id=ua.availability_id WHERE ua.user_id=%s""", (uid,))
    avail = [r['label'] for r in cur.fetchall()]
    cur.execute("""SELECT COUNT(*) c FROM swaps WHERE status='COMPLETED' AND (sender_id=%s OR receiver_id=%s)""", (uid, uid))
    completed = cur.fetchone()['c']
    cur.execute("SELECT AVG(rating) avgr, COUNT(*) c FROM feedback WHERE reviewed_id=%s", (uid,))
    r = cur.fetchone()
    rating = float(r['avgr']) if r['avgr'] is not None else 0
    rating_count = r['c']
    return {
        'id': str(uid),
        'fname': row['first_name'],
        'lname': row['last_name'] or '',
        'email': row['email'],
        'role': row['role'],
        'location': row['location'],
        'bio': row['bio'],
        'avatar': row['avatar_url'] or '',
        'visibility': row['visibility'],
        'banned': bool(row['is_banned']),
        'banReason': row['ban_reason'],
        'joinDate': iso(row['join_date'])[:10] if row['join_date'] else None,
        'availability': avail,
        'skillsOffer': offer,
        'skillsWant': want,
        'completedSwaps': completed,
        'rating': rating,
        'ratingCount': rating_count,
    }


def serialize_swap(row):
    return {
        'id': str(row['swap_id']),
        'senderId': str(row['sender_id']),
        'receiverId': str(row['receiver_id']),
        'skillOffered': row['skill_offered'],
        'skillWanted': row['skill_wanted'],
        'message': row['message'] or '',
        'status': row['status'],
        'meetingLink': row['meeting_link'] or '',
        'createdAt': iso(row['created_at']),
        'updatedAt': iso(row['updated_at']),
    }


def serialize_feedback(row):
    return {
        'id': str(row['feedback_id']),
        'swapId': str(row['swap_id']),
        'reviewerId': str(row['reviewer_id']),
        'reviewedId': str(row['reviewed_id']),
        'rating': row['rating'],
        'comment': row['comment'] or '',
        'date': iso(row['created_at']),
    }


def serialize_notif(row):
    return {
        'id': str(row['notification_id']),
        'userId': str(row['user_id']),
        'type': row['notif_type'],
        'text': row['notif_text'],
        'read': bool(row['is_read']),
        'date': iso(row['created_at']),
    }


def serialize_ann(row):
    return {
        'id': str(row['announcement_id']),
        'title': row['title'],
        'message': row['message'],
        'date': iso(row['created_at']),
        'status': row['status'],
        'adminId': str(row['admin_id']),
    }


def serialize_flag(row):
    return {
        'id': str(row['flag_id']),
        'userId': str(row['user_id']),
        'skillName': row['skill_name'],
        'type': row['flag_type'],
        'reason': row['reason'],
        'status': row['status'],
        'date': iso(row['created_at']),
    }


def add_notification(cur, user_id, ntype, text):
    cur.execute(
        "INSERT INTO notifications (user_id, notif_type, notif_text, is_read) VALUES (%s,%s,%s,0)",
        (user_id, ntype, text)
    )


def get_or_create_skill(cur, name):
    cur.execute("SELECT skill_id FROM skills WHERE skill_name=%s", (name,))
    row = cur.fetchone()
    if row:
        return row['skill_id']
    cur.execute("INSERT INTO skills (skill_name) VALUES (%s)", (name,))
    return cur.lastrowid


# ─────────────────────────────────────────────────────────────
#  Static frontend
# ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'skillswap.html')


@app.route('/api/health')
def health():
    db_status = 'disconnected'
    err_msg = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        db_status = 'connected'
    except Exception as e:
        err_msg = str(e)
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'error': err_msg
    })


@app.route('/api/init-db')
def api_init_db():
    try:
        msg = init_db()
        return jsonify({'status': 'ok', 'message': msg})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(force=True)
    fname = (data.get('fname') or '').strip()
    lname = (data.get('lname') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    location = (data.get('location') or '').strip()

    if not fname or not email or not password:
        return jsonify({'error': 'Please fill required fields'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM users WHERE email=%s", (email,))
            if cur.fetchone():
                return jsonify({'error': 'Email already registered'}), 409
            cur.execute(
                """INSERT INTO users (first_name,last_name,email,password_hash,role,location,visibility,is_banned,join_date)
                   VALUES (%s,%s,%s,%s,'user',%s,'public',0,CURDATE())""",
                (fname, lname, email, generate_password_hash(password), location)
            )
            uid = cur.lastrowid
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
            user = serialize_user(cur, row)
        session['user_id'] = uid
        session['role'] = user['role']
        return jsonify(user)
    finally:
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(force=True)
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not email or not password:
        return jsonify({'error': 'Please enter email and password'}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            row = cur.fetchone()
            if not row or not check_password_hash(row['password_hash'], password):
                return jsonify({'error': 'Invalid email or password'}), 401
            if row['is_banned']:
                return jsonify({'error': 'Your account has been banned. Contact support.'}), 403
            user = serialize_user(cur, row)
        session['user_id'] = row['user_id']
        session['role'] = row['role']
        return jsonify(user)
    finally:
        conn.close()


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/session', methods=['GET'])
def get_session():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            row = current_user_row(cur)
            if not row:
                return jsonify(None)
            return jsonify(serialize_user(cur, row))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  USERS
# ─────────────────────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
@login_required
def list_users():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users ORDER BY user_id")
            rows = cur.fetchall()
            return jsonify([serialize_user(cur, r) for r in rows])
    finally:
        conn.close()


@app.route('/api/users/<int:uid>', methods=['GET'])
@login_required
def get_user(uid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'User not found'}), 404
            return jsonify(serialize_user(cur, row))
    finally:
        conn.close()


@app.route('/api/users/<int:uid>', methods=['PUT'])
@login_required
def update_user(uid):
    if session['user_id'] != uid and session.get('role') != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'User not found'}), 404
            fname = data.get('fname', row['first_name']) or row['first_name']
            lname = data.get('lname', row['last_name'])
            bio = data.get('bio', row['bio'])
            location = data.get('location', row['location'])
            visibility = data.get('visibility', row['visibility'])
            cur.execute(
                """UPDATE users SET first_name=%s,last_name=%s,bio=%s,location=%s,visibility=%s
                   WHERE user_id=%s""",
                (fname, lname, bio, location, visibility, uid)
            )
            if 'availability' in data:
                cur.execute("DELETE FROM user_availability WHERE user_id=%s", (uid,))
                for label in data['availability']:
                    if label in AVAILABILITY_LABELS:
                        cur.execute("SELECT availability_id FROM availability_options WHERE label=%s", (label,))
                        arow = cur.fetchone()
                        if arow:
                            cur.execute(
                                "INSERT IGNORE INTO user_availability (user_id, availability_id) VALUES (%s,%s)",
                                (uid, arow['availability_id'])
                            )
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
            return jsonify(serialize_user(cur, row))
    finally:
        conn.close()


@app.route('/api/users/<int:uid>/skills', methods=['POST'])
@login_required
def add_user_skill(uid):
    if session['user_id'] != uid:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(force=True)
    skill_type = data.get('type')
    name = (data.get('skill') or '').strip()
    if skill_type not in ('offer', 'want') or not name:
        return jsonify({'error': 'Invalid skill'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT s.skill_name FROM user_skills us JOIN skills s ON s.skill_id=us.skill_id
                           WHERE us.user_id=%s AND us.skill_type=%s""", (uid, skill_type))
            existing = [r['skill_name'].lower() for r in cur.fetchall()]
            if name.lower() in existing:
                return jsonify({'error': 'Skill already added'}), 409
            sid = get_or_create_skill(cur, name)
            cur.execute(
                "INSERT INTO user_skills (user_id, skill_id, skill_type) VALUES (%s,%s,%s)",
                (uid, sid, skill_type)
            )
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
            return jsonify(serialize_user(cur, row))
    finally:
        conn.close()


@app.route('/api/users/<int:uid>/ban', methods=['PATCH'])
@admin_required
def ban_user(uid):
    data = request.get_json(force=True)
    banned = bool(data.get('banned'))
    reason = data.get('reason') or None
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET is_banned=%s, ban_reason=%s WHERE user_id=%s",
                (1 if banned else 0, reason if banned else None, uid)
            )
            cur.execute("SELECT * FROM users WHERE user_id=%s", (uid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'User not found'}), 404
            return jsonify(serialize_user(cur, row))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  SWAPS
# ─────────────────────────────────────────────────────────────
@app.route('/api/swaps', methods=['GET'])
@login_required
def list_swaps():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if session.get('role') == 'admin':
                cur.execute("SELECT * FROM swaps ORDER BY created_at DESC")
            else:
                cur.execute(
                    "SELECT * FROM swaps WHERE sender_id=%s OR receiver_id=%s ORDER BY created_at DESC",
                    (session['user_id'], session['user_id'])
                )
            return jsonify([serialize_swap(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/swaps', methods=['POST'])
@login_required
def create_swap():
    data = request.get_json(force=True)
    receiver_id = data.get('receiverId')
    skill_offered = (data.get('skillOffered') or '').strip()
    skill_wanted = (data.get('skillWanted') or '').strip()
    message = (data.get('message') or '').strip()
    sender_id = session['user_id']

    if not receiver_id or not skill_offered or not skill_wanted:
        return jsonify({'error': 'Please select both skills'}), 400
    if int(receiver_id) == sender_id:
        return jsonify({'error': 'You cannot swap with yourself'}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT swap_id FROM swaps WHERE sender_id=%s AND receiver_id=%s AND status='PENDING'",
                (sender_id, receiver_id)
            )
            if cur.fetchone():
                return jsonify({'error': 'You already have a pending request with this user'}), 409

            cur.execute(
                """INSERT INTO swaps (sender_id,receiver_id,skill_offered,skill_wanted,message,status)
                   VALUES (%s,%s,%s,%s,%s,'PENDING')""",
                (sender_id, receiver_id, skill_offered, skill_wanted, message)
            )
            swap_id = cur.lastrowid
            cur.execute("SELECT first_name, last_name FROM users WHERE user_id=%s", (sender_id,))
            sender = cur.fetchone()
            add_notification(
                cur, receiver_id, 'swap_received',
                f"{sender['first_name']} {sender['last_name']} sent you a swap request: {skill_offered} ↔ {skill_wanted}."
            )
            cur.execute("SELECT * FROM swaps WHERE swap_id=%s", (swap_id,))
            return jsonify(serialize_swap(cur.fetchone()))
    finally:
        conn.close()


@app.route('/api/swaps/<int:sid>', methods=['PATCH'])
@login_required
def update_swap(sid):
    data = request.get_json(force=True)
    status = data.get('status')
    if status not in ('ACCEPTED', 'REJECTED', 'CANCELLED'):
        return jsonify({'error': 'Invalid status'}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM swaps WHERE swap_id=%s", (sid,))
            sw = cur.fetchone()
            if not sw:
                return jsonify({'error': 'Swap not found'}), 404
            uid = session['user_id']
            if uid not in (sw['sender_id'], sw['receiver_id']) and session.get('role') != 'admin':
                return jsonify({'error': 'Forbidden'}), 403

            cur.execute("UPDATE swaps SET status=%s WHERE swap_id=%s", (status, sid))
            cur.execute("SELECT first_name, last_name FROM users WHERE user_id=%s", (uid,))
            actor = cur.fetchone()
            if status == 'ACCEPTED':
                add_notification(cur, sw['sender_id'], 'swap_accepted',
                                  f"{actor['first_name']} {actor['last_name']} accepted your swap request!")
            elif status == 'REJECTED':
                add_notification(cur, sw['sender_id'], 'swap_rejected',
                                  f"{actor['first_name']} {actor['last_name']} declined your swap request.")
            cur.execute("SELECT * FROM swaps WHERE swap_id=%s", (sid,))
            return jsonify(serialize_swap(cur.fetchone()))
    finally:
        conn.close()


@app.route('/api/swaps/<int:sid>/complete', methods=['PATCH'])
@login_required
def complete_swap(sid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM swaps WHERE swap_id=%s", (sid,))
            sw = cur.fetchone()
            if not sw:
                return jsonify({'error': 'Swap not found'}), 404
            uid = session['user_id']
            if uid not in (sw['sender_id'], sw['receiver_id']) and session.get('role') != 'admin':
                return jsonify({'error': 'Forbidden'}), 403
            cur.execute("UPDATE swaps SET status='COMPLETED' WHERE swap_id=%s", (sid,))
            other = sw['receiver_id'] if uid == sw['sender_id'] else sw['sender_id']
            add_notification(cur, other, 'swap_completed', 'A swap has been marked as completed.')
            cur.execute("SELECT * FROM swaps WHERE swap_id=%s", (sid,))
            return jsonify(serialize_swap(cur.fetchone()))
    finally:
        conn.close()


@app.route('/api/swaps/<int:sid>/meeting-link', methods=['PATCH'])
@login_required
def set_meeting_link(sid):
    data = request.get_json(force=True)
    link = (data.get('meetingLink') or '').strip()

    if link and not link.startswith('https://meet.google.com/'):
        return jsonify({'error': 'Please paste a valid meet.google.com link'}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM swaps WHERE swap_id=%s", (sid,))
            sw = cur.fetchone()
            if not sw:
                return jsonify({'error': 'Swap not found'}), 404
            uid = session['user_id']
            if uid not in (sw['sender_id'], sw['receiver_id']) and session.get('role') != 'admin':
                return jsonify({'error': 'Forbidden'}), 403
            if sw['status'] != 'ACCEPTED':
                return jsonify({'error': 'Meeting links can only be set on active swaps'}), 400

            cur.execute("UPDATE swaps SET meeting_link=%s WHERE swap_id=%s", (link or None, sid))

            if link:
                other = sw['receiver_id'] if uid == sw['sender_id'] else sw['sender_id']
                cur.execute("SELECT first_name, last_name FROM users WHERE user_id=%s", (uid,))
                actor = cur.fetchone()
                add_notification(
                    cur, other, 'meeting_link',
                    f"{actor['first_name']} {actor['last_name']} shared a Google Meet link for your swap."
                )

            cur.execute("SELECT * FROM swaps WHERE swap_id=%s", (sid,))
            return jsonify(serialize_swap(cur.fetchone()))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  FEEDBACK
# ─────────────────────────────────────────────────────────────
@app.route('/api/feedback', methods=['GET'])
@login_required
def list_feedback():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM feedback ORDER BY created_at DESC")
            return jsonify([serialize_feedback(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/feedback', methods=['POST'])
@login_required
def create_feedback():
    data = request.get_json(force=True)
    swap_id = data.get('swapId')
    reviewed_id = data.get('reviewedId')
    rating = data.get('rating')
    comment = (data.get('comment') or '').strip()
    reviewer_id = session['user_id']

    if not swap_id or not reviewed_id or not rating:
        return jsonify({'error': 'Please select a rating'}), 400
    if not comment:
        return jsonify({'error': 'Please write some feedback'}), 400

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT feedback_id FROM feedback WHERE swap_id=%s AND reviewer_id=%s",
                (swap_id, reviewer_id)
            )
            if cur.fetchone():
                return jsonify({'error': 'Feedback already submitted'}), 409
            cur.execute(
                """INSERT INTO feedback (swap_id,reviewer_id,reviewed_id,rating,comment)
                   VALUES (%s,%s,%s,%s,%s)""",
                (swap_id, reviewer_id, reviewed_id, rating, comment)
            )
            fid = cur.lastrowid
            cur.execute("SELECT first_name, last_name FROM users WHERE user_id=%s", (reviewer_id,))
            reviewer = cur.fetchone()
            add_notification(cur, reviewed_id, 'feedback',
                              f"{reviewer['first_name']} {reviewer['last_name']} left you {rating}-star feedback!")
            cur.execute("SELECT * FROM feedback WHERE feedback_id=%s", (fid,))
            return jsonify(serialize_feedback(cur.fetchone()))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  NOTIFICATIONS
# ─────────────────────────────────────────────────────────────
@app.route('/api/notifications', methods=['GET'])
@login_required
def list_notifications():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC",
                (session['user_id'],)
            )
            return jsonify([serialize_notif(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/notifications/<int:nid>/read', methods=['PATCH'])
@login_required
def mark_notif_read(nid):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notifications SET is_read=1 WHERE notification_id=%s AND user_id=%s",
                (nid, session['user_id'])
            )
            return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/api/notifications/read-all', methods=['PATCH'])
@login_required
def mark_all_read():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notifications SET is_read=1 WHERE user_id=%s",
                (session['user_id'],)
            )
            return jsonify({'ok': True})
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  ANNOUNCEMENTS
# ─────────────────────────────────────────────────────────────
@app.route('/api/announcements', methods=['GET'])
@login_required
def list_announcements():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM announcements ORDER BY created_at DESC")
            return jsonify([serialize_ann(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/announcements', methods=['POST'])
@admin_required
def create_announcement():
    data = request.get_json(force=True)
    title = (data.get('title') or '').strip()
    message = (data.get('message') or '').strip()
    if not title or not message:
        return jsonify({'error': 'Please fill all fields'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO announcements (title,message,status,admin_id) VALUES (%s,%s,'active',%s)",
                (title, message, session['user_id'])
            )
            aid = cur.lastrowid
            cur.execute("SELECT user_id FROM users WHERE role='user'")
            for r in cur.fetchall():
                add_notification(cur, r['user_id'], 'announcement', f"📢 {title}")
            cur.execute("SELECT * FROM announcements WHERE announcement_id=%s", (aid,))
            return jsonify(serialize_ann(cur.fetchone()))
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  SKILL MODERATION (flagged content)
# ─────────────────────────────────────────────────────────────
@app.route('/api/skill-flags', methods=['GET'])
@admin_required
def list_skill_flags():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM skill_flags ORDER BY created_at DESC")
            return jsonify([serialize_flag(r) for r in cur.fetchall()])
    finally:
        conn.close()


@app.route('/api/skill-flags/<int:fid>', methods=['PATCH'])
@admin_required
def moderate_skill_flag(fid):
    data = request.get_json(force=True)
    action = data.get('status')
    if action not in ('approved', 'rejected'):
        return jsonify({'error': 'Invalid action'}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE skill_flags SET status=%s, reviewed_by=%s, reviewed_at=NOW() WHERE flag_id=%s",
                (action, session['user_id'], fid)
            )
            cur.execute("SELECT * FROM skill_flags WHERE flag_id=%s", (fid,))
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'Flag not found'}), 404
            return jsonify(serialize_flag(row))
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(debug=True, port=5000)
