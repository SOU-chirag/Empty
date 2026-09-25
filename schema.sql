-- ============================================================
-- SKILLSWAP DATABASE — MySQL 8.x
-- Matches skillswap_schema.pdf / skillswap_database_documentation.pdf
-- ============================================================
DROP DATABASE IF EXISTS skillswap_db;
CREATE DATABASE IF NOT EXISTS skillswap_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE skillswap_db;

-- 1. USERS
CREATE TABLE users (
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

-- 2. SKILLS
CREATE TABLE skills (
  skill_id    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  skill_name  VARCHAR(150) NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_skills_name UNIQUE (skill_name)
) ENGINE=InnoDB;

-- 3. USER_SKILLS (junction)
CREATE TABLE user_skills (
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

-- 4. AVAILABILITY_OPTIONS (lookup)
CREATE TABLE availability_options (
  availability_id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  label           VARCHAR(50) NOT NULL,
  CONSTRAINT uq_availability_label UNIQUE (label)
) ENGINE=InnoDB;

-- 5. USER_AVAILABILITY (junction)
CREATE TABLE user_availability (
  user_id         BIGINT UNSIGNED NOT NULL,
  availability_id TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (user_id, availability_id),
  CONSTRAINT fk_ua_user  FOREIGN KEY (user_id)         REFERENCES users(user_id)                     ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_ua_avail FOREIGN KEY (availability_id) REFERENCES availability_options(availability_id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- 6. SWAPS
CREATE TABLE swaps (
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
  CONSTRAINT chk_swap_parties CHECK(sender_id <> receiver_id),
  INDEX idx_swap_sender (sender_id),
  INDEX idx_swap_receiver (receiver_id),
  INDEX idx_swap_status (status),
  INDEX idx_swap_created (created_at)
) ENGINE=InnoDB;

-- 7. FEEDBACK
CREATE TABLE feedback (
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
  CONSTRAINT chk_fb_rating  CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT chk_fb_parties CHECK (reviewer_id <> reviewed_id),
  CONSTRAINT uq_fb_swap_reviewer UNIQUE (swap_id, reviewer_id),
  INDEX idx_fb_reviewed (reviewed_id),
  INDEX idx_fb_reviewer (reviewer_id)
) ENGINE=InnoDB;

-- 8. NOTIFICATIONS
CREATE TABLE notifications (
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

-- 9. ANNOUNCEMENTS
CREATE TABLE announcements (
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

-- 10. SKILL_FLAGS (moderation queue)
CREATE TABLE skill_flags (
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

-- ============================================================
-- SEED DATA
-- Passwords below are placeholders — the backend re-hashes real
-- passwords with werkzeug's password hasher at first run via
-- seed.py, so use that script instead of these hashes if you
-- want the demo accounts (user@demo.com / pass123, etc.) to work.
-- ============================================================

INSERT INTO availability_options (label) VALUES
('Weekdays'),('Weekends'),('Mornings'),('Afternoons'),('Evenings'),('Custom');

INSERT INTO skills (skill_name) VALUES
('Java'),('Spring Boot'),('Python'),('UI/UX Design'),('Photoshop'),('Graphic Design'),
('Photography'),('Excel'),('Public Speaking'),('Data Analysis'),('Video Editing'),
('English Speaking'),('Creative Writing'),('Digital Marketing'),('Canva'),
('Accounting'),('Tally'),('JavaScript'),('React'),('CSS');

-- NOTE: users, swaps, feedback, notifications, announcements and skill_flags
-- seed rows are inserted by backend/seed.py (so passwords are hashed
-- correctly). Run: python seed.py  after creating the schema.
