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


-- ==============================================================================
-- 🚨 HOW TO FIX SUPABASE ROW LEVEL SECURITY (RLS) FOR RAILWAY BACKEND
-- ==============================================================================
-- Because you enabled Row Level Security (RLS) on Supabase, direct inserts and
-- queries from Railway (using DATABASE_URL) will be BLOCKED by default unless you
-- either create a permissive policy or disable RLS for these tables.
--
-- Choose ONE of the following options and run it in Supabase SQL Editor:
--
-- ------------------------------------------------------------------------------
-- OPTION A: Disable RLS for these tables (Recommended & Safest for Backend-Only DB)
-- Since only your secure Railway Backend (guarded by X-API-Token) will access
-- these tables, you can safely turn off RLS:
-- ------------------------------------------------------------------------------
ALTER TABLE chats DISABLE ROW LEVEL SECURITY;
ALTER TABLE memories DISABLE ROW LEVEL SECURITY;


-- ------------------------------------------------------------------------------
-- OPTION B: Keep RLS Enabled but Create Permissive Policies
-- If you want to keep RLS active, you must allow all operations for both tables
-- so that Railway can query and insert:
-- ------------------------------------------------------------------------------
-- For chats table:
-- CREATE POLICY "Allow all operations on chats" ON chats FOR ALL USING (true) WITH CHECK (true);

-- For memories table:
-- CREATE POLICY "Allow all operations on memories" ON memories FOR ALL USING (true) WITH CHECK (true);
