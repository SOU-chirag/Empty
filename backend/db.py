import os
from urllib.parse import urlparse, unquote
import pymysql
import pymysql.cursors


def get_db_config():
    """Resolve database configuration from DATABASE_URL or individual environment variables."""
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('MYSQL_URL')
    if db_url:
        parsed = urlparse(db_url)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 3306
        user = unquote(parsed.username) if parsed.username else 'root'
        password = unquote(parsed.password) if parsed.password else ''
        database = parsed.path.lstrip('/') if parsed.path else 'skillswap_db'
    else:
        host = os.environ.get('DB_HOST', 'localhost')
        port = int(os.environ.get('DB_PORT', '3306'))
        user = os.environ.get('DB_USER', 'root')
        password = os.environ.get('DB_PASSWORD', '')
        database = os.environ.get('DB_NAME', 'skillswap_db')

    config = {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database,
        'cursorclass': pymysql.cursors.DictCursor,
        'autocommit': True,
        'charset': 'utf8mb4',
    }

    # Enable SSL for remote cloud databases (Aiven, TiDB Cloud, Railway, PlanetScale, etc.)
    db_ssl = os.environ.get('DB_SSL', '').strip().lower()
    is_remote = host not in ('localhost', '127.0.0.1')
    if db_ssl in ('true', '1', 'yes', 'required') or (is_remote and db_ssl != 'false'):
        config['ssl'] = {'check_hostname': False}

    return config


def get_conn():
    """Open a fresh connection. Cursor returns rows as dicts."""
    config = get_db_config()
    return pymysql.connect(**config)


TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS users (
      user_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      first_name     VARCHAR(100)  NOT NULL,
      last_name      VARCHAR(100)  NOT NULL DEFAULT '',
      email          VARCHAR(255)  NOT NULL,
      password_hash  VARCHAR(255)  NOT NULL,
      role           ENUM('user','admin') NOT NULL DEFAULT 'user',
      location       VARCHAR(150)  NULL,
      bio            TEXT          NULL,
      avatar_url     VARCHAR(500)  NULL,
      visibility     ENUM('public','private') NOT NULL DEFAULT 'public',
      is_banned      TINYINT(1)    NOT NULL DEFAULT 0,
      ban_reason     VARCHAR(500)  NULL,
      join_date      DATE          NOT NULL,
      created_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      CONSTRAINT uq_users_email UNIQUE (email),
      INDEX idx_users_role (role),
      INDEX idx_users_banned (is_banned)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS skills (
      skill_id    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      skill_name  VARCHAR(150) NOT NULL,
      created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT uq_skills_name UNIQUE (skill_name)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS user_skills (
      user_skill_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      user_id       BIGINT UNSIGNED NOT NULL,
      skill_id      BIGINT UNSIGNED NOT NULL,
      skill_type    ENUM('offer','want') NOT NULL,
      created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_us_user  FOREIGN KEY (user_id)  REFERENCES users(user_id)   ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_us_skill FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT uq_user_skill_type UNIQUE (user_id, skill_id, skill_type),
      INDEX idx_us_skill (skill_id),
      INDEX idx_us_type (skill_type)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS availability_options (
      availability_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      label           VARCHAR(50) NOT NULL,
      CONSTRAINT uq_availability_label UNIQUE (label)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS user_availability (
      user_id         BIGINT UNSIGNED NOT NULL,
      availability_id TINYINT UNSIGNED NOT NULL,
      PRIMARY KEY (user_id, availability_id),
      CONSTRAINT fk_ua_user  FOREIGN KEY (user_id)         REFERENCES users(user_id)                     ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_ua_avail FOREIGN KEY (availability_id) REFERENCES availability_options(availability_id) ON DELETE CASCADE ON UPDATE CASCADE
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS swaps (
      swap_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      sender_id      BIGINT UNSIGNED NOT NULL,
      receiver_id    BIGINT UNSIGNED NOT NULL,
      skill_offered  VARCHAR(150) NOT NULL,
      skill_wanted   VARCHAR(150) NOT NULL,
      message        TEXT NULL,
      status         ENUM('PENDING','ACCEPTED','REJECTED','CANCELLED','COMPLETED') NOT NULL DEFAULT 'PENDING',
      meeting_link   VARCHAR(500) NULL,
      created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      CONSTRAINT fk_swap_sender   FOREIGN KEY (sender_id)   REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_swap_receiver FOREIGN KEY (receiver_id) REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
      INDEX idx_swap_sender (sender_id),
      INDEX idx_swap_receiver (receiver_id),
      INDEX idx_swap_status (status),
      INDEX idx_swap_created (created_at)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS feedback (
      feedback_id  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      swap_id      BIGINT UNSIGNED NOT NULL,
      reviewer_id  BIGINT UNSIGNED NOT NULL,
      reviewed_id  BIGINT UNSIGNED NOT NULL,
      rating       TINYINT UNSIGNED NOT NULL,
      comment      TEXT NULL,
      created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_fb_swap     FOREIGN KEY (swap_id)     REFERENCES swaps(swap_id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_fb_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_fb_reviewed FOREIGN KEY (reviewed_id) REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT uq_fb_swap_reviewer UNIQUE (swap_id, reviewer_id),
      INDEX idx_fb_reviewed (reviewed_id),
      INDEX idx_fb_reviewer (reviewer_id)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS notifications (
      notification_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      user_id          BIGINT UNSIGNED NOT NULL,
      notif_type       ENUM('swap_received','swap_accepted','swap_rejected','swap_completed','feedback','announcement') NOT NULL,
      notif_text       VARCHAR(500) NOT NULL,
      is_read          TINYINT(1) NOT NULL DEFAULT 0,
      created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
      INDEX idx_notif_user_read (user_id, is_read),
      INDEX idx_notif_created (created_at)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS announcements (
      announcement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      title           VARCHAR(200) NOT NULL,
      message         TEXT NOT NULL,
      status          ENUM('active','inactive') NOT NULL DEFAULT 'active',
      admin_id        BIGINT UNSIGNED NOT NULL,
      created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      CONSTRAINT fk_ann_admin FOREIGN KEY (admin_id) REFERENCES users(user_id) ON DELETE RESTRICT ON UPDATE CASCADE,
      INDEX idx_ann_status (status)
    ) ENGINE=InnoDB;
    """,
    """
    CREATE TABLE IF NOT EXISTS skill_flags (
      flag_id      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      user_id      BIGINT UNSIGNED NOT NULL,
      skill_name   VARCHAR(150) NOT NULL,
      flag_type    ENUM('offer','want') NOT NULL DEFAULT 'offer',
      reason       VARCHAR(500) NOT NULL,
      status       ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
      reviewed_by  BIGINT UNSIGNED NULL,
      created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
      reviewed_at  TIMESTAMP NULL,
      CONSTRAINT fk_flag_user  FOREIGN KEY (user_id)     REFERENCES users(user_id) ON DELETE CASCADE ON UPDATE CASCADE,
      CONSTRAINT fk_flag_admin FOREIGN KEY (reviewed_by) REFERENCES users(user_id) ON DELETE SET NULL ON UPDATE CASCADE,
      INDEX idx_flag_status (status),
      INDEX idx_flag_user (user_id)
    ) ENGINE=InnoDB;
    """
]


def init_db(force_seed=False):
    """Create tables if missing and seed initial lookup data & demo users."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1. Create tables
            for query in TABLES_SQL:
                cur.execute(query.strip())

            # Ensure meeting_link exists in swaps if swaps was created prior
            try:
                cur.execute("SHOW COLUMNS FROM swaps LIKE 'meeting_link'")
                if not cur.fetchone():
                    cur.execute("ALTER TABLE swaps ADD COLUMN meeting_link VARCHAR(500) NULL AFTER status")
            except Exception:
                pass

            # 2. Populate default availability options
            default_avail = ['Weekdays', 'Weekends', 'Mornings', 'Afternoons', 'Evenings', 'Custom']
            for label in default_avail:
                cur.execute("INSERT IGNORE INTO availability_options (label) VALUES (%s)", (label,))

            # 3. Populate default skills
            default_skills = [
                'Java', 'Spring Boot', 'Python', 'UI/UX Design', 'Photoshop', 'Graphic Design',
                'Photography', 'Excel', 'Public Speaking', 'Data Analysis', 'Video Editing',
                'English Speaking', 'Creative Writing', 'Digital Marketing', 'Canva',
                'Accounting', 'Tally', 'JavaScript', 'React', 'CSS'
            ]
            for sname in default_skills:
                cur.execute("INSERT IGNORE INTO skills (skill_name) VALUES (%s)", (sname,))

            # 4. Seed demo users if table is empty or forced
            cur.execute("SELECT COUNT(*) AS c FROM users")
            user_count = cur.fetchone()['c']
            if user_count == 0 or force_seed:
                try:
                    import seed
                    seed.run()
                    return "Database tables created and demo data seeded successfully."
                except Exception as se:
                    return f"Tables created, but seeding failed: {se}"

            return "Database tables and lookup data verified."
    finally:
        conn.close()
