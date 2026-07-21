import os
import json
import asyncio
from typing import Dict, List, Optional

# Local files paths for persistent storage
CHATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chats.json")
MEMORIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.json")

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

class LocalFirstDatabaseHelper:
    """
    A 100% database-free, local-first helper that manages chat histories and
    memories entirely in RAM and persists them locally as structured JSON files.

    This avoids any external database connection delay, network issues, or
    Supabase RLS/timeout blockages, making the backend completely independent.
    """
    def __init__(self):
        # Load initial local records into cache memory on startup
        self.chats: Dict[str, dict] = _load_json_file(CHATS_FILE, {})
        self.memories: Dict[str, list] = _load_json_file(MEMORIES_FILE, {"facts": []})
        print(f"[Local-First DB] Successfully initialized. Loaded {len(self.chats)} chats and {len(self.memories.get('facts', []))} memories.")

    async def get_all_chats(self) -> List[dict]:
        """Returns metadata list of all active chat sessions."""
        async with _file_lock:
            # Sort sessions chronologically if they have messages
            return [{"id": cid, "title": info["title"]} for cid, info in self.chats.items()]

    async def get_chat_history(self, chat_id: str) -> dict:
        """Fetch full chat title and message list for a specific session."""
        async with _file_lock:
            if chat_id in self.chats:
                return self.chats[chat_id]
            return {"title": "New Chat", "messages": []}

    async def save_chat_history(self, chat_id: str, title: str, messages: List[dict]) -> None:
        """Stores the updated list of messages for a session and persists atomically."""
        async with _file_lock:
            self.chats[chat_id] = {"title": title, "messages": messages}
            _save_json_file(CHATS_FILE, self.chats)

    async def delete_chat_session(self, chat_id: str) -> bool:
        """Deletes a chat session from memory and updates persistence."""
        async with _file_lock:
            if chat_id in self.chats:
                del self.chats[chat_id]
                _save_json_file(CHATS_FILE, self.chats)
                return True
            return False

    async def rename_chat_session(self, chat_id: str, title: str) -> bool:
        """Renames a chat session title."""
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
