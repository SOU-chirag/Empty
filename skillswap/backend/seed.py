"""
Run once after creating the schema (schema.sql) to load demo data,
including the demo accounts used by the wireframe:
  user@demo.com  / pass123   (member)
  admin@demo.com / admin123  (administrator)

Usage:
  python seed.py
"""
from werkzeug.security import generate_password_hash
from db import get_conn


def run():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM users")
        if cur.fetchone()['c'] > 0:
            print("Users already exist — skipping seed. Delete rows first if you want to reseed.")
            return

        users = [
            ('Alex', 'Sharma', 'alex@demo.com', 'pass123', 'user', 'Ahmedabad, India',
             'Full-stack dev who loves teaching Java and Spring Boot.', 'public', '2024-11-10'),
            ('Priya', 'Patel', 'priya@demo.com', 'pass123', 'user', 'Mumbai, India',
             'Graphic designer & photographer with 5 years of experience.', 'public', '2024-11-15'),
            ('Rahul', 'Gupta', 'rahul@demo.com', 'pass123', 'user', 'Delhi, India',
             'Data analyst and Excel power user.', 'public', '2024-12-01'),
            ('Sara', 'Khan', 'sara@demo.com', 'pass123', 'user', 'Bangalore, India',
             'English teacher and public speaker.', 'public', '2024-12-10'),
            ('Vikram', 'Singh', 'vikram@demo.com', 'pass123', 'user', 'Hyderabad, India',
             'Video editor and content creator.', 'public', '2024-12-20'),
            ('Meera', 'Nair', 'meera@demo.com', 'pass123', 'user', 'Chennai, India',
             'Finance professional and Excel guru.', 'private', '2025-01-05'),
            ('Demo', 'User', 'user@demo.com', 'pass123', 'user', 'Pune, India',
             'I love learning new skills and meeting interesting people!', 'public', '2025-01-10'),
            ('Admin', '', 'admin@demo.com', 'admin123', 'admin', None, None, 'public', '2024-10-01'),
        ]
        ids = {}
        for fname, lname, email, pw, role, loc, bio, vis, joined in users:
            cur.execute(
                """INSERT INTO users
                   (first_name,last_name,email,password_hash,role,location,bio,visibility,is_banned,join_date)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s)""",
                (fname, lname, email, generate_password_hash(pw), role, loc, bio, vis, joined)
            )
            ids[email] = cur.lastrowid

        def uid(email):
            return ids[email]

        def skill_id(cur, name):
            cur.execute("SELECT skill_id FROM skills WHERE skill_name=%s", (name,))
            row = cur.fetchone()
            if row:
                return row['skill_id']
            cur.execute("INSERT INTO skills (skill_name) VALUES (%s)", (name,))
            return cur.lastrowid

        def avail_id(cur, label):
            cur.execute("SELECT availability_id FROM availability_options WHERE label=%s", (label,))
            return cur.fetchone()['availability_id']

        user_skills = {
            'alex@demo.com':   {'offer': ['Java', 'Spring Boot', 'Python'], 'want': ['UI/UX Design', 'Photoshop']},
            'priya@demo.com':  {'offer': ['Photoshop', 'Graphic Design', 'Photography'], 'want': ['Java', 'Excel', 'Public Speaking']},
            'rahul@demo.com':  {'offer': ['Excel', 'Data Analysis', 'Python'], 'want': ['Video Editing', 'Graphic Design']},
            'sara@demo.com':   {'offer': ['English Speaking', 'Public Speaking', 'Creative Writing'], 'want': ['Python', 'Digital Marketing']},
            'vikram@demo.com': {'offer': ['Video Editing', 'Digital Marketing', 'Canva'], 'want': ['Java', 'Public Speaking', 'Photography']},
            'meera@demo.com':  {'offer': ['Excel', 'Accounting', 'Tally'], 'want': ['Photoshop', 'Video Editing']},
            'user@demo.com':   {'offer': ['JavaScript', 'React', 'CSS'], 'want': ['Photoshop', 'Public Speaking']},
        }
        for email, groups in user_skills.items():
            for stype, names in groups.items():
                for name in names:
                    sid = skill_id(cur, name)
                    cur.execute(
                        "INSERT IGNORE INTO user_skills (user_id, skill_id, skill_type) VALUES (%s,%s,%s)",
                        (uid(email), sid, stype)
                    )

        user_avail = {
            'alex@demo.com': ['Weekends', 'Evenings'],
            'priya@demo.com': ['Weekdays', 'Mornings'],
            'rahul@demo.com': ['Weekdays', 'Afternoons'],
            'sara@demo.com': ['Evenings', 'Weekends'],
            'vikram@demo.com': ['Weekends'],
            'meera@demo.com': ['Weekdays'],
            'user@demo.com': ['Weekends', 'Evenings'],
        }
        for email, labels in user_avail.items():
            for label in labels:
                cur.execute(
                    "INSERT IGNORE INTO user_availability (user_id, availability_id) VALUES (%s,%s)",
                    (uid(email), avail_id(cur, label))
                )

        swaps = [
            (uid('alex@demo.com'), uid('priya@demo.com'), 'Java', 'Photoshop',
             'Hi Priya! I can teach Java fundamentals in exchange for Photoshop basics.',
             'COMPLETED', '2025-01-15 10:00:00', '2025-02-01 10:00:00'),
            (uid('priya@demo.com'), uid('alex@demo.com'), 'Graphic Design', 'Spring Boot',
             'Would love to learn Spring Boot! Can offer Graphic Design tips.',
             'ACCEPTED', '2025-02-10 09:00:00', '2025-02-12 10:00:00'),
            (uid('rahul@demo.com'), uid('sara@demo.com'), 'Excel', 'Public Speaking',
             'Excel for Public Speaking — sounds like a fair trade!',
             'PENDING', '2025-02-20 14:00:00', '2025-02-20 14:00:00'),
            (uid('vikram@demo.com'), uid('alex@demo.com'), 'Video Editing', 'Python',
             'I can teach video editing if you can help me with Python scripting.',
             'PENDING', '2025-03-01 11:00:00', '2025-03-01 11:00:00'),
            (uid('user@demo.com'), uid('priya@demo.com'), 'JavaScript', 'Photoshop',
             'I can teach React/JS if you can help me with Photoshop basics.',
             'PENDING', '2025-03-05 09:00:00', '2025-03-05 09:00:00'),
            (uid('sara@demo.com'), uid('vikram@demo.com'), 'English Speaking', 'Video Editing',
             'Teaching English in exchange for video editing skills!',
             'COMPLETED', '2025-01-20 08:00:00', '2025-02-05 08:00:00'),
            (uid('alex@demo.com'), uid('rahul@demo.com'), 'Python', 'Data Analysis',
             'Python for Data Analysis?',
             'REJECTED', '2025-01-10 10:00:00', '2025-01-12 10:00:00'),
        ]
        swap_ids = []
        for sender, receiver, offered, wanted, msg, status, created, updated in swaps:
            cur.execute(
                """INSERT INTO swaps (sender_id,receiver_id,skill_offered,skill_wanted,message,status,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (sender, receiver, offered, wanted, msg, status, created, updated)
            )
            swap_ids.append(cur.lastrowid)

        feedback = [
            (swap_ids[0], uid('alex@demo.com'), uid('priya@demo.com'), 5,
             'Priya is an amazing teacher! Learned Photoshop basics in just 2 sessions.', '2025-02-02 10:00:00'),
            (swap_ids[0], uid('priya@demo.com'), uid('alex@demo.com'), 4,
             'Alex explained Java concepts very clearly. Patient and knowledgeable.', '2025-02-02 11:00:00'),
            (swap_ids[5], uid('sara@demo.com'), uid('vikram@demo.com'), 5,
             'Vikram helped me create a professional YouTube reel. Highly recommended!', '2025-02-06 08:00:00'),
            (swap_ids[5], uid('vikram@demo.com'), uid('sara@demo.com'), 5,
             'Sara improved my presentation skills significantly.', '2025-02-06 09:00:00'),
        ]
        for swap_id, reviewer, reviewed, rating, comment, created in feedback:
            cur.execute(
                """INSERT INTO feedback (swap_id,reviewer_id,reviewed_id,rating,comment,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (swap_id, reviewer, reviewed, rating, comment, created)
            )

        notifications = [
            (uid('user@demo.com'), 'swap_received', 'Alex Sharma sent you a swap request for Photoshop ↔ JavaScript.', 0, '2025-03-05 09:01:00'),
            (uid('user@demo.com'), 'announcement', 'SkillSwap is now live! Invite your friends to join.', 0, '2025-02-01 10:00:00'),
            (uid('priya@demo.com'), 'swap_received', 'Demo User wants to swap JavaScript ↔ Photoshop.', 0, '2025-03-05 09:01:00'),
            (uid('alex@demo.com'), 'swap_accepted', 'Priya Patel accepted your Graphic Design ↔ Spring Boot swap!', 0, '2025-02-12 10:00:00'),
        ]
        for user_id, ntype, text, read, created in notifications:
            cur.execute(
                """INSERT INTO notifications (user_id,notif_type,notif_text,is_read,created_at)
                   VALUES (%s,%s,%s,%s,%s)""",
                (user_id, ntype, text, read, created)
            )

        announcements = [
            ('Welcome to SkillSwap!', 'We are thrilled to launch SkillSwap — the peer-to-peer skill exchange platform. Start browsing, connect with others, and grow together!', '2025-02-01 10:00:00'),
            ('New skill categories now available', 'We have added Digital Marketing, Photography, and Creative Writing to our skill directory. Update your profile today!', '2025-02-15 10:00:00'),
            ('Scheduled maintenance', 'Scheduled maintenance tonight from 11 PM to 12 AM. The platform may be briefly unavailable.', '2025-03-01 08:00:00'),
        ]
        for title, message, created in announcements:
            cur.execute(
                """INSERT INTO announcements (title,message,status,admin_id,created_at)
                   VALUES (%s,%s,'active',%s,%s)""",
                (title, message, uid('admin@demo.com'), created)
            )

        skill_flags = [
            (uid('rahul@demo.com'), 'Get-rich-quick scheme teaching', 'offer', 'Suspicious commercial content', '2025-03-01 10:00:00'),
            (uid('vikram@demo.com'), 'Spam SEO tricks', 'offer', 'Potential spam', '2025-03-03 10:00:00'),
        ]
        for user_id, skill_name, ftype, reason, created in skill_flags:
            cur.execute(
                """INSERT INTO skill_flags (user_id,skill_name,flag_type,reason,status,created_at)
                   VALUES (%s,%s,%s,%s,'pending',%s)""",
                (user_id, skill_name, ftype, reason, created)
            )

    conn.close()
    print("Seed complete. Demo logins: user@demo.com/pass123, admin@demo.com/admin123 (and alex/priya/rahul/sara/vikram/meera @demo.com, all pass123).")


if __name__ == '__main__':
    run()
