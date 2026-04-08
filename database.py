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
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
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
               emotion_secondary, confidence_primary, confidence_secondary):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dreams
                    (user_id, text, interpretation, emotion_primary,
                     emotion_secondary, confidence_primary, confidence_secondary)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (user_id, text, interpretation, emotion_primary,
                  emotion_secondary, confidence_primary, confidence_secondary))
            dream_id = cur.fetchone()[0]
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
                 emotion_secondary, confidence_primary, confidence_secondary):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE dreams SET
                    text=%s, interpretation=%s, emotion_primary=%s,
                    emotion_secondary=%s, confidence_primary=%s,
                    confidence_secondary=%s
                WHERE id=%s AND user_id=%s
            """, (text, interpretation, emotion_primary, emotion_secondary,
                  confidence_primary, confidence_secondary, dream_id, user_id))
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
