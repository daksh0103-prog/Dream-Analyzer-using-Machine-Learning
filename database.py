import os
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone


def get_conn():
    return psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")


def init_db():
    """Create all tables if they don't exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS dreams (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    text TEXT NOT NULL,
                    interpretation TEXT,
                    emotion_primary TEXT,
                    emotion_secondary TEXT,
                    confidence_primary REAL DEFAULT 0,
                    confidence_secondary REAL DEFAULT 0,
                    sleep_quality INTEGER DEFAULT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS dream_symbols (
                    id SERIAL PRIMARY KEY,
                    dream_id INTEGER REFERENCES dreams(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL
                );
            """)
            # Migrate: add sleep_quality column if it doesn't exist yet
            cur.execute("""
                ALTER TABLE dreams ADD COLUMN IF NOT EXISTS sleep_quality INTEGER DEFAULT NULL;
            """)
            # Migrate: add OAuth columns to users if not present
            cur.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS oauth_id TEXT UNIQUE DEFAULT NULL;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT DEFAULT NULL;
            """)
        conn.commit()


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(username, password):
    hashed = generate_password_hash(password)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed)
            )
        conn.commit()


def get_or_create_oauth_user(oauth_id: str, username: str, email: str):
    """Find existing user by oauth_id, or create a new one (no password)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Try matching by oauth_id
            cur.execute("SELECT * FROM users WHERE oauth_id = %s", (oauth_id,))
            user = cur.fetchone()
            if user:
                return user

            # 2. Try matching by email (user may have registered manually before)
            if email:
                cur.execute("SELECT * FROM users WHERE email = %s", (email,))
                user = cur.fetchone()
                if user:
                    # Attach oauth_id to existing account
                    cur.execute(
                        "UPDATE users SET oauth_id = %s WHERE id = %s",
                        (oauth_id, user["id"])
                    )
                    conn.commit()
                    cur.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
                    return cur.fetchone()

            # 3. Create new OAuth user — ensure unique username
            base = username
            suffix = 0
            while True:
                candidate = base if suffix == 0 else f"{base}{suffix}"
                cur.execute("SELECT id FROM users WHERE username = %s", (candidate,))
                if not cur.fetchone():
                    break
                suffix += 1
            cur.execute(
                "INSERT INTO users (username, password, oauth_id, email) VALUES (%s, %s, %s, %s) RETURNING *",
                (candidate, "", oauth_id, email)
            )
            new_user = cur.fetchone()
        conn.commit()
    return new_user


def get_user(username):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            return cur.fetchone()


def get_user_by_id(user_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()


def verify_password(username, password):
    user = get_user(username)
    if user and check_password_hash(user["password"], password):
        return user
    return None


# ── Dreams ─────────────────────────────────────────────────────────────────────

def save_dream(user_id, text, interpretation, emotion_primary,
               emotion_secondary, confidence_primary, confidence_secondary,
               sleep_quality=None, symbols=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dreams
                    (user_id, text, interpretation, emotion_primary,
                     emotion_secondary, confidence_primary, confidence_secondary,
                     sleep_quality)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (user_id, text, interpretation, emotion_primary,
                  emotion_secondary, confidence_primary, confidence_secondary,
                  sleep_quality))
            dream_id = cur.fetchone()[0]
            if symbols:
                for sym in symbols:
                    cur.execute(
                        "INSERT INTO dream_symbols (dream_id, user_id, symbol) VALUES (%s,%s,%s)",
                        (dream_id, user_id, sym.lower().strip())
                    )
        conn.commit()
    return dream_id


def get_dreams(user_id, limit=100):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM dreams WHERE user_id = %s
                ORDER BY created_at DESC LIMIT %s
            """, (user_id, limit))
            return cur.fetchall()


def get_dream(dream_id, user_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM dreams WHERE id = %s AND user_id = %s",
                (dream_id, user_id)
            )
            return cur.fetchone()


def update_dream(dream_id, user_id, text, interpretation, emotion_primary,
                 emotion_secondary, confidence_primary, confidence_secondary,
                 sleep_quality=None, symbols=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE dreams SET
                    text=%s, interpretation=%s, emotion_primary=%s,
                    emotion_secondary=%s, confidence_primary=%s,
                    confidence_secondary=%s, sleep_quality=%s
                WHERE id=%s AND user_id=%s
            """, (text, interpretation, emotion_primary, emotion_secondary,
                  confidence_primary, confidence_secondary, sleep_quality,
                  dream_id, user_id))
            # Replace symbols
            cur.execute("DELETE FROM dream_symbols WHERE dream_id=%s", (dream_id,))
            if symbols:
                for sym in symbols:
                    cur.execute(
                        "INSERT INTO dream_symbols (dream_id, user_id, symbol) VALUES (%s,%s,%s)",
                        (dream_id, user_id, sym.lower().strip())
                    )
        conn.commit()


def delete_dream(dream_id, user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM dreams WHERE id=%s AND user_id=%s",
                (dream_id, user_id)
            )
        conn.commit()


# ── Analytics ──────────────────────────────────────────────────────────────────

def get_emotion_counts(user_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT emotion_primary AS emotion, COUNT(*) AS count
                FROM dreams WHERE user_id=%s AND emotion_primary IS NOT NULL
                GROUP BY emotion_primary ORDER BY count DESC
            """, (user_id,))
            return cur.fetchall()


def get_streak(user_id):
    """Return current consecutive-day streak."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT DATE(created_at AT TIME ZONE 'UTC') AS day
                FROM dreams WHERE user_id=%s
                ORDER BY day DESC
            """, (user_id,))
            days = [r[0] for r in cur.fetchall()]

    if not days:
        return 0

    streak = 1
    for i in range(1, len(days)):
        if (days[i - 1] - days[i]).days == 1:
            streak += 1
        else:
            break
    return streak


def get_mood_calendar(user_id):
    """Return list of {day, emotion} for the last 90 days."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC') AS day,
                    emotion_primary AS emotion
                FROM dreams
                WHERE user_id=%s
                  AND created_at >= NOW() - INTERVAL '90 days'
                ORDER BY day ASC
            """, (user_id,))
            return cur.fetchall()


def get_sleep_emotion_data(user_id):
    """Return list of {sleep_quality, emotion_primary} where sleep_quality is set."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT sleep_quality, emotion_primary,
                       DATE(created_at AT TIME ZONE 'UTC') AS day
                FROM dreams
                WHERE user_id=%s AND sleep_quality IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 60
            """, (user_id,))
            return cur.fetchall()


def get_top_symbols(user_id, limit=20):
    """Return top recurring dream symbols for a user."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT symbol, COUNT(*) AS count
                FROM dream_symbols
                WHERE user_id=%s
                GROUP BY symbol
                ORDER BY count DESC
                LIMIT %s
            """, (user_id, limit))
            return cur.fetchall()
