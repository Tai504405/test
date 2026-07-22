import os
import re
import sqlite3
import json
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime

logger = logging.getLogger(__name__)

class SqliteCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, sql, params=None):
        if params is None:
            self.cursor.execute(sql)
        else:
            self.cursor.execute(sql, params)
        return self

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
        
    def __iter__(self):
        return iter(self.cursor)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        self._lastrowid = None

    def execute(self, sql, params=None):
        # Translate '?' to '%s' for PostgreSQL
        sql_translated = sql.replace('?', '%s')
        
        # If it's an INSERT and does not contain RETURNING, append RETURNING id
        is_insert = re.match(r'^\s*INSERT\s+INTO', sql_translated, re.IGNORECASE) is not None
        if is_insert and 'returning' not in sql_translated.lower():
            sql_translated += ' RETURNING id'
            
        if params is None:
            self.cursor.execute(sql_translated)
        else:
            self.cursor.execute(sql_translated, params)
            
        if is_insert:
            try:
                row = self.cursor.fetchone()
                if row:
                    self._lastrowid = row[0]
            except Exception:
                pass
        return self

    @property
    def lastrowid(self):
        return self._lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
        
    def __iter__(self):
        return iter(self.cursor)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

class HybridConnection:
    def __init__(self, conn, is_postgres=False):
        self._conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        cur = self._conn.cursor()
        if self.is_postgres:
            return PostgresCursorWrapper(cur)
        return SqliteCursorWrapper(cur)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)

def get_db_connection(db_path: str = "database.db"):
    """Returns a HybridConnection object configuring it for PostgreSQL or SQLite depending on the environment."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if db_url:
        if db_url.startswith("postgres://") or db_url.startswith("postgresql://"):
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            try:
                conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)
                return HybridConnection(conn, is_postgres=True)
            except Exception as e:
                logger.warning(f"Không thể kết nối Supabase PostgreSQL ({str(e)}). Chuyển sang dùng SQLite local: {db_path}")
            
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return HybridConnection(conn, is_postgres=False)

def init_db(db_path: str = "database.db"):
    """Creates the SQLite or PostgreSQL schema tables if they do not exist."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    if conn.is_postgres:
        # 1. runs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id SERIAL PRIMARY KEY,
            account_id TEXT NOT NULL,
            status TEXT NOT NULL, -- PENDING, HUMAN_REVIEW, APPROVED, REJECTED, PUBLISHED
            model_route TEXT NOT NULL,
            total_prompt_tokens INTEGER DEFAULT 0,
            total_completion_tokens INTEGER DEFAULT 0,
            total_cost REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # 2. drafts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id SERIAL PRIMARY KEY,
            run_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            rewrite_attempt INTEGER NOT NULL,
            score REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
        )
        """)
        
        # 3. critic_results table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS critic_results (
            id SERIAL PRIMARY KEY,
            draft_id INTEGER NOT NULL,
            passed INTEGER NOT NULL, -- 0 or 1
            violations TEXT NOT NULL, -- JSON string list of violation messages
            violation_codes TEXT NOT NULL, -- JSON string list of error codes
            FOREIGN KEY (draft_id) REFERENCES drafts (id) ON DELETE CASCADE
        )
        """)
    else:
        # 1. runs table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            status TEXT NOT NULL, -- PENDING, HUMAN_REVIEW, APPROVED, REJECTED, PUBLISHED
            model_route TEXT NOT NULL,
            total_prompt_tokens INTEGER DEFAULT 0,
            total_completion_tokens INTEGER DEFAULT 0,
            total_cost REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # 2. drafts table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            rewrite_attempt INTEGER NOT NULL,
            score REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
        )
        """)
        
        # 3. critic_results table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS critic_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id INTEGER NOT NULL,
            passed INTEGER NOT NULL, -- 0 or 1
            violations TEXT NOT NULL, -- JSON string list of violation messages
            violation_codes TEXT NOT NULL, -- JSON string list of error codes
            FOREIGN KEY (draft_id) REFERENCES drafts (id) ON DELETE CASCADE
        )
        """)
    
    conn.commit()
    conn.close()

def seed_mock_data(db_path: str = "database.db"):
    """Populates the database with realistic mock data to demonstrate the human review queue, rewrite attempts, and statistics."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Clear existing data first
    cursor.execute("DELETE FROM critic_results")
    cursor.execute("DELETE FROM drafts")
    cursor.execute("DELETE FROM runs")
    conn.commit()
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Run 1: threads_10xlab (HUMAN_REVIEW) - Has 2 rewrite attempts
    # Attempt 1: Violated "synergy" and length too short
    # Attempt 2: Valid, waiting for review
    cursor.execute("""
    INSERT INTO runs (account_id, status, model_route, total_prompt_tokens, total_completion_tokens, total_cost, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("threads_10xlab", "HUMAN_REVIEW", "gemini-1.5-flash", 1200, 450, 0.0012, now, now))
    run1_id = cursor.lastrowid
    
    # Attempt 1
    cursor.execute("""
    INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (run1_id, "We need to drive synergy across all dev teams. #productivity", 1, 0.45, now))
    draft1_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
    VALUES (?, ?, ?, ?)
    """, (draft1_id, 0, 
          json.dumps(["Nội dung quá ngắn (59 ký tự, yêu cầu tối thiểu 100 ký tự).", "Bài viết chứa từ bị cấm: 'synergy'."]), 
          json.dumps(["LENGTH_TOO_SHORT", "BANNED_WORD_PRESENT"])))
          
    # Attempt 2 (waiting for review)
    cursor.execute("""
    INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (run1_id, "Just spent 3 hours refactoring a Python script into a Go tool. The speedup is real! We are making great progress on optimization. #productivity", 2, 0.88, now))
    draft2_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
    VALUES (?, ?, ?, ?)
    """, (draft2_id, 1, json.dumps([]), json.dumps([])))
    

    # Run 2: x_dev (HUMAN_REVIEW) - Has 1 attempt
    # Attempt 1: Violated excessive emojis (maximum 1 emoji per post)
    cursor.execute("""
    INSERT INTO runs (account_id, status, model_route, total_prompt_tokens, total_completion_tokens, total_cost, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("x_dev", "HUMAN_REVIEW", "gemini-1.5-flash", 800, 180, 0.0006, now, now))
    run2_id = cursor.lastrowid
    
    cursor.execute("""
    INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (run2_id, "Python tip: Use zip(strict=True) in Python 3.10+ to catch mismatched list lengths early! 🚀🐍 #python", 1, 0.72, now))
    draft3_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
    VALUES (?, ?, ?, ?)
    """, (draft3_id, 0, 
          json.dumps(["Bài viết chứa quá nhiều emoji (2 emoji, yêu cầu tối đa: 1)."]), 
          json.dumps(["TOO_MANY_EMOJIS"])))


    # Run 3: facebook_tech (APPROVED) - Has 1 attempt
    # Already approved by operator
    cursor.execute("""
    INSERT INTO runs (account_id, status, model_route, total_prompt_tokens, total_completion_tokens, total_cost, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("facebook_tech", "APPROVED", "gemini-1.5-pro", 2500, 950, 0.0085, now, now))
    run3_id = cursor.lastrowid
    
    cursor.execute("""
    INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (run3_id, (
        "Have you ever wondered how databases handle concurrent writes without messing up your data? "
        "It comes down to ACID transactions. Specifically, Isolation levels like Read Committed or Serializable. "
        "Let's break them down today. Isolation levels control the visibility of changes made by one transaction to other concurrent transactions. "
        "Higher isolation levels reduce concurrency anomalies but increase contention and lock waits.\n"
        "What isolation level do you use in your production databases?"
    ), 1, 0.95, now))
    draft4_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
    VALUES (?, ?, ?, ?)
    """, (draft4_id, 1, json.dumps([]), json.dumps([])))


    # Run 4: threads_10xlab (REJECTED) - Has 1 attempt
    # Already rejected by operator
    cursor.execute("""
    INSERT INTO runs (account_id, status, model_route, total_prompt_tokens, total_completion_tokens, total_cost, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("threads_10xlab", "REJECTED", "gemini-1.5-flash", 1000, 300, 0.0009, now, now))
    run4_id = cursor.lastrowid
    
    cursor.execute("""
    INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (run4_id, "This new software system is revolutionizing the paradigm shift in our daily work. Buy it now!", 1, 0.30, now))
    draft5_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
    VALUES (?, ?, ?, ?)
    """, (draft5_id, 0, 
          json.dumps(["Nội dung quá ngắn (86 ký tự, yêu cầu tối thiểu 100 ký tự).", 
                      "Bài viết chứa từ bị cấm: 'paradigm shift'.",
                      "Bài viết chứa liên kết/link (không được phép)."]), 
          json.dumps(["LENGTH_TOO_SHORT", "BANNED_WORD_PRESENT", "LINKS_NOT_ALLOWED"])))

    # Run 5: x_dev (PUBLISHED) - Has 2 attempts
    # Already published
    cursor.execute("""
    INSERT INTO runs (account_id, status, model_route, total_prompt_tokens, total_completion_tokens, total_cost, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("x_dev", "PUBLISHED", "gemini-1.5-flash", 1500, 400, 0.0013, now, now))
    run5_id = cursor.lastrowid
    
    # Attempt 1 (failed)
    cursor.execute("""
    INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (run5_id, "Rust tips: Pattern matching makes code super readable.", 1, 0.65, now))
    draft6_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
    VALUES (?, ?, ?, ?)
    """, (draft6_id, 0, json.dumps(["Bài viết chứa quá ít hashtag (0 hashtags, yêu cầu tối thiểu: 1)."]), json.dumps(["TOO_FEW_HASHTAGS"])))
    
    # Attempt 2 (published)
    cursor.execute("""
    INSERT INTO drafts (run_id, content, rewrite_attempt, score, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (run5_id, "Rust tip: Pattern matching on enums makes code robust and clean. Use it to prevent unhandled cases. #rust", 2, 0.90, now))
    draft7_id = cursor.lastrowid
    cursor.execute("""
    INSERT INTO critic_results (draft_id, passed, violations, violation_codes)
    VALUES (?, ?, ?, ?)
    """, (draft7_id, 1, json.dumps([]), json.dumps([])))

    conn.commit()
    conn.close()
    print("Seed mock data successfully!")

if __name__ == "__main__":
    init_db()
    seed_mock_data()
