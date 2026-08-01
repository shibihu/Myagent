# 🤖 MyAgent — AI Chat + Autonomous IDE Agent

A full-stack AI assistant platform built on FastAPI, featuring a sleek chat UI, a persistent memory system, an autonomous IDE agent, and deep MCP (Model Context Protocol) integration for connecting external tools like **Files Manager** and **GitHub**.

---

## 🚀 Features

- **Real-time Streaming Chat** — SSE-based streaming with status callbacks so you see the agent thinking live
- **Persistent Memory** — Automatically extracts and stores facts about the user across conversations via an async background task
- **Autonomous IDE Agent** — Multi-step agent that can read, write, patch, and execute files in a sandboxed workspace
- **MCP Tool Integration** — Plug in any MCP server (Files Manager, GitHub, Roblox Studio, and more) via `mcp_config.json`
- **GitHub Import** — Clone any public or private repo directly into the agent workspace using a PAT
- **File Upload Support** — Attach `.txt`, `.pdf`, and images directly in the chat for the agent to read
- **PWA Ready** — Installable as a Progressive Web App via `manifest.json`
- **Markdown + Syntax Highlighting** — Responses rendered with `marked.js` + `highlight.js` (GitHub Dark theme)

---

## 📂 Project Structure

```text
├── app.py                  # FastAPI entry point — all routes and endpoints
├── config.py               # Environment variable loading
├── database.py             # DB helper for chat history and memory persistence
├── schema.sql              # Database schema
├── mcp_config.json         # MCP server configuration (edit to add tools)
├── agent/
│   ├── agent.py            # Core ChatAgent — sends messages, handles streaming
│   ├── ide_agent.py        # IDEAgent — autonomous multi-step task runner
│   ├── tools.py            # Low-level tools: read/write/patch file, execute command, git ops
│   ├── mcp_loader.py       # Loads and validates mcp_config.json at runtime
│   └── mcp_registry.py     # MCP server registry and tool dispatcher
├── static/                 # CSS and JavaScript assets
├── templates/              # Jinja2 HTML templates
├── requirements.txt        # Python dependencies
└── Dockerfile              # Container build
```

---

## ▶️ Run Locally

```bash
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## 🔐 Environment Variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
API_SECRET_TOKEN=your_secure_token_here   # Guards the /api/* IDE endpoints
```

> If `GROQ_API_KEY` is missing, the app starts gracefully and returns a friendly error instead of crashing.

---

## 🔌 MCP Integration Guide

MyAgent uses the **Model Context Protocol** to give the AI access to external tools at runtime. Tools are declared in `mcp_config.json` and loaded automatically on startup.

### Understanding `mcp_config.json`

```json
{
  "mcpServers": {
    "server-name": {
      "url": "http://localhost:PORT"
    }
  }
}
```

Each key under `mcpServers` is a named tool server. The agent will query it for available tools and invoke them on demand.

---

### 📁 Files Manager MCP — Best Practices

The **Files Manager MCP** gives the agent the ability to read, write, list, and move files inside the workspace. To use it optimally:

#### 1. Register it in `mcp_config.json`

```json
{
  "mcpServers": {
    "files-manager": {
      "url": "http://localhost:3001"
    }
  }
}
```

#### 2. Prefer specific file paths over broad reads

```
✅ Good:  "Read the file at src/config.py and summarize the settings"
❌ Avoid: "Read everything in the project"
```

#### 3. Use the write tool for edits, not patches, when replacing whole files

```
✅ Good:  "Rewrite requirements.txt with these packages: ..."
✅ Good:  "Patch lines 10–20 of app.py to add error handling"
❌ Avoid: Pasting entire file contents into the chat to ask for edits
```

#### 4. Verify directory structure before bulk operations

Ask the agent to run `view_dir` first so it knows the workspace layout before writing or moving files:

```
"First show me the directory structure, then update the Dockerfile."
```

#### 5. Always confirm destructive operations

The `write_file` tool overwrites without a trash can. Before running it on important files, ask:

```
"Preview what the new content will look like before writing it."
```

#### 6. Updating `mcp_config.json` via the UI

The app exposes a live config editor at **Settings → MCP Config** in the chat UI, or via the API:

```bash
# GET current config
curl http://localhost:8000/api/mcp/config

# POST new config
curl -X POST http://localhost:8000/api/mcp/config \
  -H "Content-Type: application/json" \
  -d '{"config_raw": "{\"mcpServers\": {\"files-manager\": {\"url\": \"http://localhost:3001\"}}}"}'
```

The endpoint validates JSON before saving — an invalid config will return a `400` error and the old config stays intact.

---

### 🐙 GitHub MCP — Best Practices

The **GitHub MCP** lets the agent browse repos, read files, open issues, and manage pull requests without you ever copy-pasting code.

#### 1. Register it in `mcp_config.json`

```json
{
  "mcpServers": {
    "github": {
      "url": "http://localhost:3002"
    }
  }
}
```

#### 2. Pass your PAT via the `X-GitHub-Token` header (never in chat)

The app is already wired to forward `X-GitHub-Token` from the browser to GitHub API calls. Set it once in your client — never paste tokens into the chat window, since chat history is stored in the database.

```js
// Example: setting the token in your frontend fetch call
fetch("/api/github/repos", {
  headers: { "X-GitHub-Token": "ghp_yourTokenHere" }
})
```

#### 3. Clone repos into the workspace before editing

```
"Clone https://github.com/myorg/myrepo into the workspace, then open README.md."
```

The agent will use the authenticated clone endpoint:

```bash
POST /api/github/clone
{ "repo_url": "https://github.com/myorg/myrepo", "token": "ghp_..." }
```

#### 4. Check `git_status` before asking the agent to make changes

```
"Run git status, then fix the failing test in tests/test_api.py."
```

This prevents the agent from committing on a dirty working tree or wrong branch.

#### 5. Use `git_rollback` as your safety net

If the agent makes a bad edit, immediately ask:

```
"Rollback the last git change."
```

This calls `git_rollback_tool()` which runs `git checkout -- .` to restore the working tree.

#### 6. Use the IDE Agent for multi-step GitHub tasks

For complex tasks (e.g., "find the bug in issue #42, fix it, and write a test"), use the high-level **IDE Agent endpoint** instead of the chat:

```bash
POST /api/agent/run
X-API-Token: your_secure_token_here

{
  "instruction": "Fix the bug described in GitHub issue #42 in the file agent/tools.py. Write a regression test and ensure all existing tests pass.",
  "max_iterations": 15
}
```

The IDE Agent will autonomously loop through read → edit → execute → verify steps and return a full report.

---

## 🛡️ Secure API Endpoints

All `/api/*` endpoints (except `/api/github/repos` and `/api/github/clone`) require the `X-API-Token` header:

```bash
curl -X POST http://localhost:8000/api/tools/view_dir \
  -H "X-API-Token: your_secure_token_here" \
  -H "Content-Type: application/json" \
  -d '{"path": "."}'
```

Set `API_SECRET_TOKEN` in your `.env` to override the default (which you should always do in production).

---

## 🧠 Memory System

The agent automatically extracts facts from each conversation and stores them in the database. You can inspect and manage memories via:

```bash
GET  /memory              # List all stored memories
DELETE /memory/{index}    # Remove a specific memory by index
```

Memories are injected into every subsequent conversation as context, so the agent remembers things like your preferred language, active project names, and coding style.

---

## ☁️ Deploy

### Docker

```bash
docker build -t myagent .
docker run -p 8000:8000 --env-file .env myagent
```

### Railway / Render

1. Connect your GitHub repo.
2. Set `GROQ_API_KEY` and `API_SECRET_TOKEN` as environment variables.
3. Use the `Dockerfile` for the build.
4. Set start command: `uvicorn app:app --host 0.0.0.0 --port 8000`

---

## 📡 Key API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Chat UI |
| `POST` | `/chat` | Send a message (supports SSE streaming) |
| `GET` | `/chats` | List all chat sessions |
| `GET` | `/chats/{id}` | Get chat history |
| `DELETE` | `/chats/{id}` | Delete a chat session |
| `PUT` | `/chats/{id}` | Rename a chat session |
| `GET` | `/memory` | View stored memories |
| `DELETE` | `/memory/{index}` | Delete a memory |
| `POST` | `/api/agent/run` 🔒 | Run the IDE Agent autonomously |
| `POST` | `/api/tools/read_file` 🔒 | Read a file from workspace |
| `POST` | `/api/tools/write_file` 🔒 | Write/overwrite a file |
| `POST` | `/api/tools/patch_file` 🔒 | Patch a specific block in a file |
| `POST` | `/api/tools/view_dir` 🔒 | List workspace directory |
| `POST` | `/api/tools/execute_command` 🔒 | Run a shell command |
| `POST` | `/api/tools/git_status` 🔒 | Get git status |
| `POST` | `/api/tools/git_rollback` 🔒 | Rollback uncommitted changes |
| `GET` | `/api/github/repos` | List GitHub repos (requires `X-GitHub-Token`) |
| `POST` | `/api/github/clone` | Clone a repo into workspace |
| `GET` | `/api/mcp/config` | View current MCP config |
| `POST` | `/api/mcp/config` | Update MCP config |

🔒 = requires `X-API-Token` header

---

## 📄 License

MIT
