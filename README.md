# SkillSwap — Full-Stack Build

Flask (Python) + MySQL 8 backend wired up behind the **exact same**
`skillswap.html` frontend (same CSS, layout, sidebar, cards, modals —
only the JavaScript data layer was touched, so it now talks to a REST
API instead of `localStorage`).

```
EXISTING FRONTEND  →  fetch()/JS  →  Flask REST API  →  MySQL
```

## What changed in the frontend, and what didn't

- **Unchanged:** every `<style>` rule, every HTML element/id/class, every
  `render*()` function, every modal, every onclick handler name.
- **Changed:** only the data layer at the top of `<script>` and the
  handful of functions that used to write straight to `localStorage`
  (`doLogin`, `doRegister`, `loginAs`, `doLogout`, `initApp`, `addSkill`,
  `saveEditProfile`, `sendSwapRequest`, `updateSwap`, `completeSwap`,
  `submitFeedback`, `markNotifRead`, `markAllRead`, `toggleBan`,
  `moderateSkill`, `publishAnnouncement`). Each of those now calls the
  Flask API via a small `api()` fetch helper, then updates an in-memory
  `CACHE` object that mirrors the old `ss_users` / `ss_swaps` /
  `ss_feedback` / `ss_notifications` / `ss_announcements` / `ss_flagged`
  collections — so every render function still reads `DB.getAll('swaps')`
  etc. exactly as before.

## Project layout

```
backend/
  app.py          Flask REST API (all endpoints)
  db.py           PyMySQL connection helper
  schema.sql      CREATE TABLE statements (matches skillswap_schema.pdf)
  seed.py         Loads the same demo users/swaps/feedback as the
                  original seedData(), with real password hashes
  requirements.txt
frontend/
  skillswap.html  Same UI, API-backed JS
```

## 1. Create the database

```bash
mysql -u root -p < backend/schema.sql
```

This creates `skillswap_db` with the `users`, `skills`, `user_skills`,
`availability_options`, `user_availability`, `swaps`, `feedback`,
`notifications`, `announcements` and `skill_flags` tables, plus the
fixed availability options and skill list.

## 2. Configure and install the backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Set DB credentials as environment variables (defaults shown):

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=yourpassword
export DB_NAME=skillswap_db
export SECRET_KEY=change-me
```

## 3. Seed demo data (optional but recommended)

```bash
python seed.py
```

Loads the same 8 demo accounts as the original app, with properly
hashed passwords:

| Email | Password | Role |
|---|---|---|
| user@demo.com | pass123 | Member |
| admin@demo.com | admin123 | Administrator |
| alex@demo.com / priya@demo.com / rahul@demo.com / sara@demo.com / vikram@demo.com / meera@demo.com | pass123 | Member |

## 4. Run

```bash
python app.py
```

Flask serves **both** the API (`/api/...`) and the frontend
(`skillswap.html` at `/`) from the same origin on `http://localhost:5000`,
so cookies/sessions work with no CORS setup needed. Open that URL in
your browser — the UI is pixel-identical to the original wireframe/HTML,
now reading and writing MySQL through Flask.

## API summary

| Feature | Endpoint |
|---|---|
| Register / Login / Logout | `POST /api/register`, `POST /api/login`, `POST /api/logout` |
| List / get / update user, add skill | `GET /api/users`, `GET /api/users/:id`, `PUT /api/users/:id`, `POST /api/users/:id/skills` |
| Ban / unban (admin) | `PATCH /api/users/:id/ban` |
| List / create swap | `GET /api/swaps`, `POST /api/swaps` |
| Accept/reject/cancel, complete | `PATCH /api/swaps/:id`, `PATCH /api/swaps/:id/complete` |
| Feedback | `GET /api/feedback`, `POST /api/feedback` |
| Notifications | `GET /api/notifications`, `PATCH /api/notifications/:id/read`, `PATCH /api/notifications/read-all` |
| Announcements (admin post) | `GET /api/announcements`, `POST /api/announcements` |
| Skill moderation (admin) | `GET /api/skill-flags`, `PATCH /api/skill-flags/:id` |

`completedSwaps`, `rating` and `ratingCount` are **computed** on every
request (via `COUNT`/`AVG` queries), matching the schema documentation's
normalization notes — they are never stored columns.

CSV report downloads (Users / Swaps / Feedback) stay client-side, built
from the already-loaded `CACHE`, exactly like the original.

## Notes / things to double check before production use

- Sessions use Flask's signed cookie (`SECRET_KEY`) — set a real secret
  and serve over HTTPS in production.
- Passwords are hashed with Werkzeug's `generate_password_hash`
  (PBKDF2). Swap in bcrypt/argon2 if you need to match the schema
  doc's `$2y$` bcrypt placeholders exactly.
- `GET /api/feedback` and `GET /api/announcements` return the full
  table to any logged-in user, matching the original app's behavior
  (all data lived in the same browser-local store with no per-user
  scoping). Tighten this if you need real access control.
