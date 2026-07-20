-- SQL Schema to create the required tables in Supabase / PostgreSQL for MyAgent

-- 1. Table for Chats History Session with chronological ordering support
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    messages JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Table for Long-term Memories Context
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    facts JSONB DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index optimization (Optional but highly recommended for fast JSON queries)
CREATE INDEX IF NOT EXISTS idx_chats_messages ON chats USING gin (messages);
CREATE INDEX IF NOT EXISTS idx_memories_facts ON memories USING gin (facts);
CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats (created_at DESC);
