import os
import json
import asyncio
from typing import Dict, List, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
import datetime

# Local files paths for persistent storage
CHATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chats.json")
MEMORIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

# Asynchronous lock to prevent concurrent write collisions and file corruption
_file_lock = asyncio.Lock()

def _load_json_file(filepath: str, default_val) -> dict:
    """Synchronously load a JSON file on startup with fallback protection."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Local-First DB] Warning: Failed to read {filepath}: {e}")
    return default_val

def _save_json_file(filepath: str, data) -> None:
    """Atomically save data to a JSON file using write-then-rename approach."""
    temp_path = filepath + ".tmp"
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(temp_path, filepath)
    except Exception as e:
        print(f"[Local-First DB] Error saving to {filepath}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

# ==============================================================================
# SQLALCHEMY ORM MODELS & DATABASE CONFIGURATION
# ==============================================================================

Base = declarative_base()

class Users(Base):
    """
    SQLAlchemy model mapping directly to the existing 'users' table in Supabase.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    github_id = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=False)
    prompt_content = Column(Text, nullable=True)

# Fetch Database URL securely from Environment
DATABASE_URL = os.getenv("DATABASE_URL")

from sqlalchemy.pool import NullPool

# Initialize Engine and SessionLocal
SessionLocal = None
engine = None

if DATABASE_URL:
    try:
        connect_args = {"connect_timeout": 5}
        if "postgresql" in DATABASE_URL.lower():
            connect_args["sslmode"] = "require"

        # Use NullPool for serverless Vercel environments to prevent connection slot exhaustion
        engine = create_engine(
            DATABASE_URL,
            poolclass=NullPool,
            connect_args=connect_args,
            pool_pre_ping=True
        )
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        # Safely create tables if they do not exist
        Base.metadata.create_all(bind=engine)
        print("[Local-First DB] SQLAlchemy connection handler initialized successfully with NullPool & SSL.")
    except Exception as e:
        print(f"[Local-First DB] Warning: Failed to initialize database engine for {DATABASE_URL}: {e}")

def check_db_connection() -> bool:
    """
    Startup health-check / ping test to verify connectivity to Supabase PostgreSQL.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[DB-Health] Database connection skipped: DATABASE_URL not set in environment.")
        return False
    try:
        connect_args = {"connect_timeout": 5}
        if "postgresql" in db_url.lower():
            connect_args["sslmode"] = "require"

        ping_engine = create_engine(
            db_url,
            poolclass=NullPool,
            connect_args=connect_args,
            pool_pre_ping=True
        )
        with ping_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[DB-Health] Database connection established successfully to Supabase PostgreSQL!")
        return True
    except Exception as e:
        print(f"[DB-Health] Database connection FAILED: {str(e)}")
        return False

# ==============================================================================
# LOCAL FIRST DATABASE HELPER WITH SUPABASE FAIL-SAFE INTEGRATION
# ==============================================================================

class LocalFirstDatabaseHelper:
    """
    A 100% database-free, local-first helper that manages chat histories and
    memories entirely in RAM and persists them locally as structured JSON files.

    If DATABASE_URL is configured, it dynamically synchronizes user records
    into the Supabase PostgreSQL 'users' table using SQLAlchemy ORM.
    """
    def __init__(self):
        # Load initial local records into cache memory on startup
        self.chats: Dict[str, dict] = _load_json_file(CHATS_FILE, {})
        self.memories: Dict[str, list] = _load_json_file(MEMORIES_FILE, {"facts": []})
        self.users: Dict[str, dict] = _load_json_file(USERS_FILE, {})
        print(f"[Local-First DB] Successfully initialized. Loaded {len(self.chats)} chats, {len(self.memories.get('facts', []))} memories, and {len(self.users)} users.")

    async def get_user(self, github_id: str) -> Optional[dict]:
        """Fetch user data by GitHub ID from Supabase PostgreSQL or fallback to local cache."""
        if SessionLocal:
            try:
                # Synchronous SQLAlchemy query inside try-except
                db = SessionLocal()
                try:
                    user_record = db.query(Users).filter(Users.github_id == str(github_id)).first()
                    if user_record:
                        # Extract email/avatar metadata from prompt_content if stored as JSON
                        email = None
                        avatar_url = None
                        if user_record.prompt_content:
                            try:
                                meta = json.loads(user_record.prompt_content)
                                if isinstance(meta, dict):
                                    email = meta.get("email")
                                    avatar_url = meta.get("avatar_url")
                            except Exception:
                                pass
                        return {
                            "github_id": user_record.github_id,
                            "username": user_record.username,
                            "email": email,
                            "avatar_url": avatar_url,
                            "created_at": user_record.created_at.isoformat() if user_record.created_at else None,
                            "prompt_content": user_record.prompt_content
                        }
                finally:
                    db.close()
            except Exception as e:
                print(f"[Local-First DB] Warning: Failed to query users from Supabase: {e}")

        # Fallback to local users.json
        async with _file_lock:
            return self.users.get(str(github_id))

    async def save_or_update_user(self, github_id: str, username: str, email: Optional[str] = None, avatar_url: Optional[str] = None) -> dict:
        """Saves or updates user records in Supabase PostgreSQL or fallback to local cache."""
        now_dt = datetime.datetime.utcnow()
        g_id = str(github_id)

        if SessionLocal:
            try:
                db = SessionLocal()
                try:
                    user_record = db.query(Users).filter(Users.github_id == g_id).first()
                    meta = {"avatar_url": avatar_url, "email": email}
                    meta_str = json.dumps(meta)

                    if user_record:
                        user_record.username = username
                        user_record.prompt_content = meta_str
                    else:
                        user_record = Users(
                            github_id=g_id,
                            username=username,
                            created_at=now_dt,
                            prompt_content=meta_str
                        )
                        db.add(user_record)
                    db.commit()
                    db.refresh(user_record)
                    return {
                        "github_id": user_record.github_id,
                        "username": user_record.username,
                        "email": email,
                        "avatar_url": avatar_url,
                        "created_at": user_record.created_at.isoformat() if user_record.created_at else None,
                        "prompt_content": user_record.prompt_content
                    }
                finally:
                    db.close()
            except Exception as e:
                print(f"[Local-First DB] Warning: Failed to save user to Supabase: {e}")

        # Fallback to local users.json file persistence
        async with _file_lock:
            if g_id in self.users:
                user = self.users[g_id]
                user["username"] = username
                user["email"] = email
                user["avatar_url"] = avatar_url
                user["last_login"] = now_dt.isoformat()
            else:
                user = {
                    "github_id": g_id,
                    "username": username,
                    "email": email,
                    "avatar_url": avatar_url,
                    "created_at": now_dt.isoformat(),
                    "last_login": now_dt.isoformat()
                }
            self.users[g_id] = user
            _save_json_file(USERS_FILE, self.users)
            return user

    async def get_all_chats(self) -> List[dict]:
        """Returns metadata list of all active chat sessions."""
        if SessionLocal:
            try:
                db = SessionLocal()
                try:
                    # Query chats sessions chronologically
                    rows = db.execute(text("SELECT id, title FROM chats ORDER BY created_at DESC")).fetchall()
                    return [{"id": str(r[0]), "title": str(r[1])} for r in rows]
                finally:
                    db.close()
            except Exception as e:
                print(f"[Local-First DB] Warning: Failed to query chats list from SQL: {e}")

        async with _file_lock:
            # Sort sessions chronologically if they have messages
            return [{"id": cid, "title": info["title"]} for cid, info in self.chats.items()]

    async def get_chat_history(self, chat_id: str) -> dict:
        """Fetch full chat title and message list for a specific session from SQL or local cache."""
        if SessionLocal:
            try:
                db = SessionLocal()
                try:
                    chat_row = db.execute(text("SELECT title FROM chats WHERE id = :cid"), {"cid": chat_id}).first()
                    title = chat_row[0] if chat_row else "New Chat"

                    # Fetch individual messages filtered strictly by chat_id
                    msg_rows = db.execute(
                        text("SELECT role, content FROM chat_messages WHERE chat_id = :cid ORDER BY created_at ASC"),
                        {"cid": chat_id}
                    ).fetchall()

                    messages = []
                    for r, c in msg_rows:
                        role = str(r)
                        # Translate 'assistant' back to 'ai' to keep chat histories fully uniform
                        if role == "assistant":
                            role = "ai"
                        messages.append({
                            "role": role,
                            "content": str(c),
                            "model": None,
                            "total_tokens": 0
                        })
                    return {"title": title, "messages": messages}
                finally:
                    db.close()
            except Exception as e:
                print(f"[Local-First DB] Warning: Failed to query chat messages from SQL: {e}")

        async with _file_lock:
            if chat_id in self.chats:
                return self.chats[chat_id]
            return {"title": "New Chat", "messages": []}

    async def save_chat_history(self, chat_id: str, title: str, messages: List[dict]) -> None:
        """Stores the updated list of messages for a session and persists atomically."""
        if SessionLocal:
            try:
                db = SessionLocal()
                try:
                    # 1. Save or Update chat metadata
                    chat_exists = db.execute(text("SELECT 1 FROM chats WHERE id = :cid"), {"cid": chat_id}).first()
                    if chat_exists:
                        db.execute(text("UPDATE chats SET title = :title WHERE id = :cid"), {"title": title, "cid": chat_id})
                    else:
                        db.execute(text("INSERT INTO chats (id, title) VALUES (:cid, :title)"), {"cid": chat_id, "title": title})

                    # 2. Re-create messages in chat_messages table to ensure consistent order without duplicates
                    db.execute(text("DELETE FROM chat_messages WHERE chat_id = :cid"), {"cid": chat_id})

                    for idx, msg in enumerate(messages):
                        msg_id = f"{chat_id}_{idx}"
                        role = msg.get("role")
                        # Translate 'ai' role to 'assistant' to satisfy database constraint check list
                        if role == "ai":
                            role = "assistant"
                        db.execute(
                            text("INSERT INTO chat_messages (id, chat_id, role, content) VALUES (:mid, :cid, :role, :content)"),
                            {"mid": msg_id, "cid": chat_id, "role": role, "content": msg.get("content")}
                        )
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                print(f"[Local-First DB] Warning: Failed to save chat messages to SQL: {e}")

        async with _file_lock:
            self.chats[chat_id] = {"title": title, "messages": messages}
            _save_json_file(CHATS_FILE, self.chats)

    async def delete_chat_session(self, chat_id: str) -> bool:
        """Deletes a chat session from memory and updates persistence."""
        if SessionLocal:
            try:
                db = SessionLocal()
                try:
                    db.execute(text("DELETE FROM chats WHERE id = :cid"), {"cid": chat_id})
                    db.execute(text("DELETE FROM chat_messages WHERE chat_id = :cid"), {"cid": chat_id})
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                print(f"[Local-First DB] Warning: Failed to delete chat from SQL: {e}")

        async with _file_lock:
            if chat_id in self.chats:
                del self.chats[chat_id]
                _save_json_file(CHATS_FILE, self.chats)
                return True
            return False

    async def rename_chat_session(self, chat_id: str, title: str) -> bool:
        """Renames a chat session title."""
        if SessionLocal:
            try:
                db = SessionLocal()
                try:
                    db.execute(text("UPDATE chats SET title = :title WHERE id = :cid"), {"title": title, "cid": chat_id})
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                print(f"[Local-First DB] Warning: Failed to rename chat in SQL: {e}")

        async with _file_lock:
            if chat_id in self.chats:
                self.chats[chat_id]["title"] = title
                _save_json_file(CHATS_FILE, self.chats)
                return True
            return False

    async def get_memories(self) -> List[str]:
        """Retrieve list of learned memory facts."""
        async with _file_lock:
            return self.memories.get("facts", [])

    async def save_memories(self, facts: List[str]) -> None:
        """Saves memory facts list."""
        async with _file_lock:
            self.memories["facts"] = facts
            _save_json_file(MEMORIES_FILE, self.memories)

db_helper = LocalFirstDatabaseHelper()
