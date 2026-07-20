import os
import json
import asyncio
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGO_URI")

# We fallback to a local dictionary if MONGO_URI is not set.
# This ensures that tests can run and local/temporary deploys don't crash.
class LocalStorageFallback:
    def __init__(self):
        self.chats: Dict[str, dict] = {}
        self.memories: Dict[str, list] = {"facts": []}

    def load_chats(self) -> dict:
        return self.chats

    def save_chats(self, data: dict):
        self.chats = data

    def load_memories(self) -> dict:
        return self.memories

    def save_memories(self, data: dict):
        self.memories = data

fallback_storage = LocalStorageFallback()

class MongoDBHelper:
    def __init__(self):
        self.client = None
        self.db = None
        if MONGO_URI:
            try:
                self.client = AsyncIOMotorClient(MONGO_URI)
                # Parse database name from URI, default to 'myagent_db'
                self.db = self.client.get_default_database(default="myagent_db")
                print("[MongoDB] Connected to database successfully.")
            except Exception as e:
                print(f"[MongoDB] Connection error: {e}. Falling back to local storage.")
                self.client = None
                self.db = None

    @property
    def is_connected(self) -> bool:
        return self.db is not None

    async def get_all_chats(self) -> List[dict]:
        """Loads all chats and returns simplified listing."""
        if not self.is_connected:
            chats_data = fallback_storage.load_chats()
            return [{"id": cid, "title": info["title"]} for cid, info in chats_data.items()]

        try:
            cursor = self.db.chats.find({}, {"_id": 1, "title": 1})
            chats = []
            async for doc in cursor:
                chats.append({"id": doc["_id"], "title": doc.get("title", "New Chat")})
            return chats
        except Exception as e:
            print(f"[MongoDB] Error get_all_chats: {e}")
            return []

    async def get_chat_history(self, chat_id: str) -> dict:
        """Retrieves a specific chat's history."""
        if not self.is_connected:
            chats_data = fallback_storage.load_chats()
            if chat_id in chats_data:
                return chats_data[chat_id]
            return {"title": "New Chat", "messages": []}

        try:
            doc = await self.db.chats.find_one({"_id": chat_id})
            if doc:
                return {"title": doc.get("title", "New Chat"), "messages": doc.get("messages", [])}
            return {"title": "New Chat", "messages": []}
        except Exception as e:
            print(f"[MongoDB] Error get_chat_history: {e}")
            return {"title": "New Chat", "messages": []}

    async def save_chat_history(self, chat_id: str, title: str, messages: List[dict]) -> None:
        """Saves or updates a chat session's history."""
        if not self.is_connected:
            chats_data = fallback_storage.load_chats()
            chats_data[chat_id] = {"title": title, "messages": messages}
            fallback_storage.save_chats(chats_data)
            return

        try:
            await self.db.chats.update_one(
                {"_id": chat_id},
                {"$set": {"title": title, "messages": messages}},
                upsert=True
            )
        except Exception as e:
            print(f"[MongoDB] Error save_chat_history: {e}")

    async def delete_chat_session(self, chat_id: str) -> bool:
        """Deletes a chat session."""
        if not self.is_connected:
            chats_data = fallback_storage.load_chats()
            if chat_id in chats_data:
                del chats_data[chat_id]
                fallback_storage.save_chats(chats_data)
                return True
            return False

        try:
            res = await self.db.chats.delete_one({"_id": chat_id})
            return res.deleted_count > 0
        except Exception as e:
            print(f"[MongoDB] Error delete_chat_session: {e}")
            return False

    async def rename_chat_session(self, chat_id: str, title: str) -> bool:
        """Renames a chat session title."""
        if not self.is_connected:
            chats_data = fallback_storage.load_chats()
            if chat_id in chats_data:
                chats_data[chat_id]["title"] = title
                fallback_storage.save_chats(chats_data)
                return True
            return False

        try:
            res = await self.db.chats.update_one(
                {"_id": chat_id},
                {"$set": {"title": title}}
            )
            return res.modified_count > 0 or res.matched_count > 0
        except Exception as e:
            print(f"[MongoDB] Error rename_chat_session: {e}")
            return False

    async def get_memories(self) -> List[str]:
        """Gets all permanent memories/facts about the user."""
        if not self.is_connected:
            return fallback_storage.load_memories().get("facts", [])

        try:
            doc = await self.db.memories.find_one({"_id": "user_memory"})
            if doc:
                return doc.get("facts", [])
            return []
        except Exception as e:
            print(f"[MongoDB] Error get_memories: {e}")
            return []

    async def save_memories(self, facts: List[str]) -> None:
        """Saves permanent memories/facts about the user."""
        if not self.is_connected:
            fallback_storage.save_memories({"facts": facts})
            return

        try:
            await self.db.memories.update_one(
                {"_id": "user_memory"},
                {"$set": {"facts": facts}},
                upsert=True
            )
        except Exception as e:
            print(f"[MongoDB] Error save_memories: {e}")

db_helper = MongoDBHelper()
