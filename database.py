import os
import json
import asyncio
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient

# For PostgreSQL support
import asyncpg

MONGO_URI = os.getenv("MONGO_URI")
DATABASE_URL = os.getenv("DATABASE_URL")

# If DATABASE_URL is standard postgres protocol (postgres://), asyncpg prefers postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Local dictionary fallback
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
    def __init__(self, uri: str):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client.get_default_database(default="myagent_db")

    async def get_all_chats(self) -> List[dict]:
        cursor = self.db.chats.find({}, {"_id": 1, "title": 1})
        chats = []
        async for doc in cursor:
            chats.append({"id": doc["_id"], "title": doc.get("title", "New Chat")})
        return chats

    async def get_chat_history(self, chat_id: str) -> dict:
        doc = await self.db.chats.find_one({"_id": chat_id})
        if doc:
            return {"title": doc.get("title", "New Chat"), "messages": doc.get("messages", [])}
        return {"title": "New Chat", "messages": []}

    async def save_chat_history(self, chat_id: str, title: str, messages: List[dict]) -> None:
        await self.db.chats.update_one(
            {"_id": chat_id},
            {"$set": {"title": title, "messages": messages}},
            upsert=True
        )

    async def delete_chat_session(self, chat_id: str) -> bool:
        res = await self.db.chats.delete_one({"_id": chat_id})
        return res.deleted_count > 0

    async def rename_chat_session(self, chat_id: str, title: str) -> bool:
        res = await self.db.chats.update_one(
            {"_id": chat_id},
            {"$set": {"title": title}}
        )
        return res.modified_count > 0 or res.matched_count > 0

    async def get_memories(self) -> List[str]:
        doc = await self.db.memories.find_one({"_id": "user_memory"})
        if doc:
            return doc.get("facts", [])
        return []

    async def save_memories(self, facts: List[str]) -> None:
        await self.db.memories.update_one(
            {"_id": "user_memory"},
            {"$set": {"facts": facts}},
            upsert=True
        )


class PostgreSQLHelper:
    def __init__(self, url: str):
        self.url = url
        self._pool = None

    async def get_pool(self):
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.url)
        return self._pool

    async def get_all_chats(self) -> List[dict]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Order chronologically by created_at timestamp
            rows = await conn.fetch("SELECT id, title FROM chats ORDER BY created_at DESC")
            return [{"id": r["id"], "title": r["title"]} for r in rows]

    async def get_chat_history(self, chat_id: str) -> dict:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT title, messages FROM chats WHERE id = $1", chat_id)
            if row:
                # asyncpg returns JSONB as Python dictionary/list natively, so we decode only if it's a string
                messages = row["messages"]
                if isinstance(messages, str):
                    try:
                        messages = json.loads(messages)
                    except Exception:
                        pass
                return {"title": row["title"], "messages": messages or []}
            return {"title": "New Chat", "messages": []}

    async def save_chat_history(self, chat_id: str, title: str, messages: List[dict]) -> None:
        pool = await self.get_pool()
        # For JSONB column on asyncpg, we must pass either Python dict/list directly, or serialize to JSON string and cast
        # Let's pass the serialized JSON string but explicitly cast it to ::jsonb in the SQL query.
        # This is extremely robust and 100% compatible with both raw string / mapped collection bindings!
        messages_json = json.dumps(messages, ensure_ascii=False)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO chats (id, title, messages)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (id)
                DO UPDATE SET title = EXCLUDED.title, messages = EXCLUDED.messages
                """,
                chat_id, title, messages_json
            )

    async def delete_chat_session(self, chat_id: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute("DELETE FROM chats WHERE id = $1", chat_id)
            return "DELETE 1" in res

    async def rename_chat_session(self, chat_id: str, title: str) -> bool:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            res = await conn.execute("UPDATE chats SET title = $2 WHERE id = $1", chat_id, title)
            return "UPDATE 1" in res or "UPDATE" in res

    async def get_memories(self) -> List[str]:
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT facts FROM memories WHERE id = 'user_memory'")
            if row:
                facts = row["facts"]
                if isinstance(facts, str):
                    try:
                        facts = json.loads(facts)
                    except Exception:
                        pass
                return facts or []
            return []

    async def save_memories(self, facts: List[str]) -> None:
        pool = await self.get_pool()
        facts_json = json.dumps(facts, ensure_ascii=False)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (id, facts)
                VALUES ('user_memory', $1::jsonb)
                ON CONFLICT (id)
                DO UPDATE SET facts = EXCLUDED.facts
                """,
                facts_json
            )


class UnifiedDatabaseHelper:
    def __init__(self):
        self.postgres = None
        self.mongo = None

        if DATABASE_URL:
            try:
                self.postgres = PostgreSQLHelper(DATABASE_URL)
                print("[Database] Using Supabase PostgreSQL Database.")
            except Exception as e:
                print(f"[Database] PostgreSQL Initialization Error: {e}")
        elif MONGO_URI:
            try:
                self.mongo = MongoDBHelper(MONGO_URI)
                print("[Database] Using MongoDB Atlas Database.")
            except Exception as e:
                print(f"[Database] MongoDB Initialization Error: {e}")
        else:
            print("[Database] No cloud DB config found. Falling back to in-memory/local mock.")

    async def get_all_chats(self) -> List[dict]:
        if self.postgres:
            try:
                return await self.postgres.get_all_chats()
            except Exception as e:
                print(f"[Supabase PG Error] get_all_chats: {e}")
        elif self.mongo:
            try:
                return await self.mongo.get_all_chats()
            except Exception as e:
                print(f"[Mongo Error] get_all_chats: {e}")

        # Fallback
        chats_data = fallback_storage.load_chats()
        return [{"id": cid, "title": info["title"]} for cid, info in chats_data.items()]

    async def get_chat_history(self, chat_id: str) -> dict:
        if self.postgres:
            try:
                return await self.postgres.get_chat_history(chat_id)
            except Exception as e:
                print(f"[Supabase PG Error] get_chat_history: {e}")
        elif self.mongo:
            try:
                return await self.mongo.get_chat_history(chat_id)
            except Exception as e:
                print(f"[Mongo Error] get_chat_history: {e}")

        # Fallback
        chats_data = fallback_storage.load_chats()
        if chat_id in chats_data:
            return chats_data[chat_id]
        return {"title": "New Chat", "messages": []}

    async def save_chat_history(self, chat_id: str, title: str, messages: List[dict]) -> None:
        if self.postgres:
            try:
                await self.postgres.save_chat_history(chat_id, title, messages)
                return
            except Exception as e:
                print(f"[Supabase PG Error] save_chat_history: {e}")
        elif self.mongo:
            try:
                await self.mongo.save_chat_history(chat_id, title, messages)
                return
            except Exception as e:
                print(f"[Mongo Error] save_chat_history: {e}")

        # Fallback
        chats_data = fallback_storage.load_chats()
        chats_data[chat_id] = {"title": title, "messages": messages}
        fallback_storage.save_chats(chats_data)

    async def delete_chat_session(self, chat_id: str) -> bool:
        if self.postgres:
            try:
                return await self.postgres.delete_chat_session(chat_id)
            except Exception as e:
                print(f"[Supabase PG Error] delete_chat_session: {e}")
        elif self.mongo:
            try:
                return await self.mongo.delete_chat_session(chat_id)
            except Exception as e:
                print(f"[Mongo Error] delete_chat_session: {e}")

        # Fallback
        chats_data = fallback_storage.load_chats()
        if chat_id in chats_data:
            del chats_data[chat_id]
            fallback_storage.save_chats(chats_data)
            return True
        return False

    async def rename_chat_session(self, chat_id: str, title: str) -> bool:
        if self.postgres:
            try:
                return await self.postgres.rename_chat_session(chat_id, title)
            except Exception as e:
                print(f"[Supabase PG Error] rename_chat_session: {e}")
        elif self.mongo:
            try:
                return await self.mongo.rename_chat_session(chat_id, title)
            except Exception as e:
                print(f"[Mongo Error] rename_chat_session: {e}")

        # Fallback
        chats_data = fallback_storage.load_chats()
        if chat_id in chats_data:
            chats_data[chat_id]["title"] = title
            fallback_storage.save_chats(chats_data)
            return True
        return False

    async def get_memories(self) -> List[str]:
        if self.postgres:
            try:
                return await self.postgres.get_memories()
            except Exception as e:
                print(f"[Supabase PG Error] get_memories: {e}")
        elif self.mongo:
            try:
                return await self.mongo.get_memories()
            except Exception as e:
                print(f"[Mongo Error] get_memories: {e}")

        # Fallback
        return fallback_storage.load_memories().get("facts", [])

    async def save_memories(self, facts: List[str]) -> None:
        if self.postgres:
            try:
                await self.postgres.save_memories(facts)
                return
            except Exception as e:
                print(f"[Supabase PG Error] save_memories: {e}")
        elif self.mongo:
            try:
                await self.mongo.save_memories(facts)
                return
            except Exception as e:
                print(f"[Mongo Error] save_memories: {e}")

        # Fallback
        fallback_storage.save_memories({"facts": facts})

db_helper = UnifiedDatabaseHelper()
