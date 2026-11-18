import sqlite3
import hashlib
import secrets
import json
from contextlib import closing
from pathlib import Path
from typing import Any

class AuthManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    profile_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            conn.commit()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def register(self, username: str, password: str, profile: dict[str, Any]) -> dict[str, Any]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return {"error": "Username already exists"}

            pwd_hash = self._hash_password(password)
            profile_json = json.dumps(profile)
            
            cursor.execute(
                "INSERT INTO users (username, password_hash, profile_json) VALUES (?, ?, ?)",
                (username, pwd_hash, profile_json)
            )
            user_id = cursor.lastrowid
            
            token = secrets.token_hex(32)
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
            conn.commit()
            
            return {"token": token, "username": username, "profile": profile}

    def login(self, username: str, password: str) -> dict[str, Any]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            pwd_hash = self._hash_password(password)
            cursor.execute("SELECT id, profile_json FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash))
            row = cursor.fetchone()
            
            if not row:
                return {"error": "Invalid username or password"}
                
            user_id, profile_json = row
            profile = json.loads(profile_json)
            
            token = secrets.token_hex(32)
            cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
            conn.commit()
            
            return {"token": token, "username": username, "profile": profile}

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
            
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT u.username, u.profile_json 
                FROM users u 
                JOIN sessions s ON u.id = s.user_id 
                WHERE s.token = ?
            """, (token,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            username, profile_json = row
            return {"username": username, "profile": json.loads(profile_json)}
