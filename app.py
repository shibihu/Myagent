import os
import re
import uuid
import json
import asyncio
import httpx
from typing import Optional, List
import io
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Form, File, UploadFile, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agent.agent import ChatAgent
from agent.ide_agent import IDEAgent
from pypdf import PdfReader

# Auth Imports
import agent.auth as auth_mod
from agent.auth import (
    create_access_token,
    get_current_user, get_current_user_or_api_client
)

# Import database module & helper
from database import db_helper

# Import tools for direct API endpoint access
from agent.tools import (
    read_file_tool, patch_file_tool, view_dir_tool,
    execute_command_tool, clone_repository_tool,
    git_status_tool, git_rollback_tool,
    write_file_tool, list_directory_tool
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Security configuration
API_SECRET_TOKEN = os.environ.get("API_SECRET_TOKEN", "super-secret-ide-agent-token-123")

async def verify_api_token(x_api_token: Optional[str] = Header(None, alias="X-API-Token")):
    """Verifies that the incoming request has the correct secret token to secure Railway endpoints."""
    if not x_api_token or x_api_token != API_SECRET_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing API security token.")

app = FastAPI()

# Configured CORS Middleware for Localhost, Vercel, and Ngrok Tunnels
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows Roblox Studio, local dev servers, and ngrok tunnels
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=[
        "*",
        "ngrok-skip-browser-warning",  # Allows bypass header for ngrok free tunnels
        "X-API-Token",
        "X-GitHub-Token"
    ],
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

agent = ChatAgent()
ide_agent = IDEAgent()

# === ระบบความจำอัตโนมัติ (Asynchronous DB Memory Extraction) ===
async def extract_and_save_memory(user_msg: str, ai_reply: str):
    extraction_prompt = f"""
    วิเคราะห์บทสนทนาล่าสุด และสกัดข้อมูลสำคัญเกี่ยวกับตัวผู้ใช้ (เช่น ภาษาโปรแกรมที่ใช้, แพลตฟอร์มที่เล่นหรือพัฒนา เช่น Roblox, ชื่อโปรเจกต์ เช่น Cookie Yummy หรือสไตล์ดีไซน์)
    
    [บทสนทนา]
    ผู้ใช้: {user_msg}
    AI: {ai_reply}
    
    กฎข้อบังคับอย่างเคร่งครัด:
    1. ตอบในรูปแบบ JSON โครงสร้างนี้เท่านั้น: {{"memories": ["ผู้ใช้ชอบ...", "ผู้ใช้กำลังทำ..."]}}
    2. ห้ามทักทาย ห้ามมีข้อความอื่นนอกเหนือจาก JSON ห้ามใส่เครื่องหมายครอบโค้ดใดยังทั้งสิ้น
    """
    
    try:
        res = await agent.get_response(extraction_prompt)
        raw_reply = res["reply"].strip()
        new_facts = []
        match = re.search(r'\{\s*["\']memories["\']\s*:\s*\[.*\]\s*\}', raw_reply, re.DOTALL)
        
        if match:
            json_content = match.group(0)
            json_content = re.sub(r"'\s*,\s*'", '", "', json_content)
            json_content = re.sub(r"\[\s*'", '["', json_content)
            json_content = re.sub(r"'\s*\]", '"]', json_content)
            
            try:
                parsed = json.loads(json_content)
                new_facts = parsed.get("memories", [])
            except json.JSONDecodeError:
                new_facts = re.findall(r'["\'](.*?)["\']', json_content)
                new_facts = [f for f in new_facts if f != "memories"]
        else:
            lines = re.findall(r'["\'](.*?)["\']', raw_reply)
            new_facts = [l.strip() for l in lines if l.strip() and l != "memories" and len(l) > 3]

        if new_facts:
            existing_list = await db_helper.get_memories()
            updated = False
            for fact in new_facts:
                if fact not in existing_list and fact.lower() != "memories":
                    existing_list.append(fact)
                    updated = True

            if updated:
                await db_helper.save_memories(existing_list)
                print(f"[Memory System DB Saved]: {new_facts}")
                
    except Exception as e:
        print(f"[Memory Extraction Fatal Exception]: {e}")

# === Pydantic Models ===
class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None

class RenameRequest(BaseModel):
    title: str

class IDEAgentRunRequest(BaseModel):
    instruction: str
    max_iterations: Optional[int] = 10

class GitHubCloneRequest(BaseModel):
    repo_url: str
    token: Optional[str] = None

class MCPConfigRequest(BaseModel):
    config_raw: str

class ReadFileRequest(BaseModel):
    filepath: str

class PatchFileRequest(BaseModel):
    filepath: str
    search_block: Optional[str] = ""
    replace_block: str

class ViewDirRequest(BaseModel):
    path: Optional[str] = "."

class ExecuteCommandRequest(BaseModel):
    command: str

class CloneRepoRequest(BaseModel):
    repo_url: str

class WriteFileRequest(BaseModel):
    filepath: str
    content: str

class ListDirectoryRequest(BaseModel):
    path: Optional[str] = "."

# === API Endpoints ===
@app.get("/")
async def index_page(request: Request):
    # Fetch NEXT_PUBLIC_API_URL if configured, so we can inject it dynamically into the index page
    backend_url = os.environ.get("NEXT_PUBLIC_API_URL", "")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "NEXT_PUBLIC_API_URL": backend_url
        }
    )

@app.get("/manifest.json")
async def get_manifest():
    """Serves the PWA manifest file."""
    return FileResponse(os.path.join(BASE_DIR, "manifest.json"), media_type="application/json")

@app.get("/favicon.ico")
async def get_favicon():
    """Serves the favicon.ico file from static directory."""
    favicon_path = os.path.join(BASE_DIR, "static", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="Favicon not found")

# ==============================================================================
# GITHUB OAUTH AUTHENTICATION ENDPOINTS
# ==============================================================================

from fastapi.responses import RedirectResponse

@app.get("/auth/github/login")
async def github_login():
    """Redirects user to GitHub's OAuth authorization URL."""
    # Use dynamic lookup to allow test patching and runtime env modifications
    client_id = os.environ.get("GITHUB_CLIENT_ID") or auth_mod.GITHUB_CLIENT_ID
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="OAuth Configuration Error: GITHUB_CLIENT_ID is not configured in backend environment."
        )
    redirect_uri = "https://github.com/login/oauth/authorize"
    scope = "read:user user:email"
    return RedirectResponse(
        url=f"{redirect_uri}?client_id={client_id}&scope={scope}"
    )

@app.get("/auth/github/callback")
async def github_callback(code: str):
    """Receives the authorization code, exchanges it for access_token, and authenticates user."""
    client_id = os.environ.get("GITHUB_CLIENT_ID") or auth_mod.GITHUB_CLIENT_ID
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET") or auth_mod.GITHUB_CLIENT_SECRET
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="OAuth Configuration Error: GitHub credentials are not configured in backend environment."
        )

    # 1. Exchange code for access_token
    token_url = "https://github.com/login/oauth/access_token"
    headers = {"Accept": "application/json"}
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(token_url, json=payload, headers=headers)
            if token_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange OAuth code with GitHub.")

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise HTTPException(status_code=400, detail=f"GitHub OAuth Error: {token_data.get('error_description', 'No access token returned.')}")

            # 2. Retrieve user profile info
            user_url = "https://api.github.com/user"
            user_headers = {
                "Authorization": f"token {access_token}",
                "User-Agent": "MyAgent-AI-Auth"
            }
            user_resp = await client.get(user_url, headers=user_headers)
            if user_resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to retrieve user profile from GitHub.")

            user_info = user_resp.json()
            github_id = user_info.get("id")
            username = user_info.get("login")
            avatar_url = user_info.get("avatar_url")
            email = user_info.get("email")

            # 3. Retrieve user email if not public in profile
            if not email:
                emails_url = "https://api.github.com/user/emails"
                emails_resp = await client.get(emails_url, headers=user_headers)
                if emails_resp.status_code == 200:
                    emails_data = emails_resp.json()
                    for email_entry in emails_data:
                        if email_entry.get("primary") and email_entry.get("verified"):
                            email = email_entry.get("email")
                            break

            # 4. Persistence: save or update user in our database layer
            user_record = await db_helper.save_or_update_user(
                github_id=github_id,
                username=username,
                email=email,
                avatar_url=avatar_url
            )

            # 5. Issue Custom Signed JWT Token
            jwt_token = create_access_token({"sub": str(github_id), "username": username})

            # 6. Set in secure cookie and redirect back to home page
            response = RedirectResponse(url="/")
            response.set_cookie(
                key="access_token",
                value=jwt_token,
                httponly=True,
                max_age=60 * 60 * 24 * 7,  # 7 days
                samesite="lax"
            )
            return response

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Authentication flow encountered fatal error: {str(e)}")

@app.get("/auth/me")
async def get_me(user = Depends(get_current_user)):
    """Protected route to fetch authenticated user profile details."""
    return user

@app.get("/auth/logout")
async def logout_user():
    """Logs out the user by clearing session cookies."""
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response

@app.get("/chats")
async def get_all_chats():
    # Return all chat sessions list
    return await db_helper.get_all_chats()

@app.get("/chats/{chat_id}")
async def get_chat_history(chat_id: str):
    return await db_helper.get_chat_history(chat_id)

@app.post("/chat")
async def chat_endpoint(
    request: Request,
    background_tasks: BackgroundTasks
):
    content_type = request.headers.get("content-type", "")
    
    message = ""
    chat_id = None
    search_web = False
    files_to_process = []
    
    if "multipart/form-data" in content_type:
        form_data = await request.form()
        message = form_data.get("message", "")
        chat_id = form_data.get("chat_id")
        search_web_val = form_data.get("search_web", "false")
        search_web = search_web_val.lower() == "true"
        files_to_process = form_data.getlist("files")
    else:
        try:
            json_data = await request.json()
            message = json_data.get("message", "")
            chat_id = json_data.get("chat_id")
            search_web = json_data.get("search_web", False)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON or request payload")

    files_context = ""
    for file in files_to_process:
        filename = file.filename
        if not filename:
            continue
        content_bytes = await file.read()
        if not content_bytes:
            continue
        ext = os.path.splitext(filename)[1].lower()
        
        if ext == ".txt":
            try:
                text_data = content_bytes.decode("utf-8", errors="ignore")
                files_context += f"\n--- Start of File: {filename} ---\n{text_data}\n--- End of File: {filename} ---\n"
            except Exception as e:
                files_context += f"\n[Error parsing TXT File {filename}: {str(e)}]\n"
        elif ext == ".pdf":
            try:
                pdf_file = io.BytesIO(content_bytes)
                reader = PdfReader(pdf_file)
                pdf_text = ""
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        pdf_text += t + "\n"
                files_context += f"\n--- Start of PDF File: {filename} ---\n{pdf_text}\n--- End of PDF File: {filename} ---\n"
            except Exception as e:
                files_context += f"\n[Error parsing PDF File {filename}: {str(e)}]\n"
        elif ext in [".jpg", ".jpeg", ".png"]:
            size_kb = len(content_bytes) / 1024
            files_context += f"\n[Attached Image File: {filename} (Size: {size_kb:.2f} KB)]\n"
        else:
            files_context += f"\n[Attached File: {filename} (Size: {len(content_bytes)} bytes)]\n"

    memories_facts = await db_helper.get_memories()
    
    cid = chat_id
    current_chat = await db_helper.get_chat_history(cid) if cid else None

    if not cid or not current_chat or not current_chat.get("messages"):
        cid = str(uuid.uuid4()) if not cid else cid
        t_msg = message if message else (files_to_process[0].filename if files_to_process else "New Chat")
        title = t_msg[:15] + "..." if len(t_msg) > 15 else t_msg
        messages = []
    else:
        title = current_chat["title"]
        messages = current_chat["messages"]

    display_message = message
    if files_to_process:
        file_names = ", ".join([f"📎 {f.filename}" for f in files_to_process if f.filename])
        if display_message:
            display_message += f"\n\n({file_names})"
        else:
            display_message = file_names

    messages.append({
        "role": "user",
        "content": display_message,
        "model": None,
        "total_tokens": 0
    })

    # Save user message to database temporarily before getting reply
    await db_helper.save_chat_history(cid, title, messages)

    agent_message = message
    if files_context:
        agent_message = f"{files_context}\n\nUser Message: {message}"

    injected_message = agent_message
    if memories_facts:
        memory_context = "\n".join([f"- {f}" for f in memories_facts])
        injected_message = f"[ข้อมูลความจำถาวรเกี่ยวกับผู้ใช้:\n{memory_context}]\n\nคำสั่งปัจจุบัน: {agent_message}"
    
    accept_header = request.headers.get("accept", "")

    # Slicing Window: slice history to only send last 10 messages for optimized token usage
    sliding_history = messages[-10:] if len(messages) > 10 else messages

    if "text/event-stream" in accept_header:
        from fastapi.responses import StreamingResponse

        async def event_generator():
            queue = asyncio.Queue()

            async def status_cb(msg: str):
                await queue.put({"type": "status", "message": msg})

            async def run_agent_task():
                try:
                    res = await agent.get_response(injected_message, history=sliding_history, status_callback=status_cb)

                    # Add result to messages history chain and save
                    messages.append({
                        "role": "ai",
                        "content": res["reply"],
                        "model": res["model"],
                        "total_tokens": res["total_tokens"]
                    })
                    await db_helper.save_chat_history(cid, title, messages)

                    # Extract memory in background
                    background_tasks.add_task(extract_and_save_memory, message, res["reply"])

                    # Send final event
                    await queue.put({
                        "type": "final",
                        "chat_id": cid,
                        "title": title,
                        "reply": res["reply"],
                        "model": res["model"],
                        "total_tokens": res["total_tokens"]
                    })
                except Exception as e:
                    await queue.put({"type": "error", "message": str(e)})
                finally:
                    await queue.put(None)

            # Spawn agent runner task
            asyncio.create_task(run_agent_task())

            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Standard JSON fallback for backward compatibility / tests
    result = await agent.get_response(injected_message, history=sliding_history)

    messages.append({
        "role": "ai",
        "content": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    })

    await db_helper.save_chat_history(cid, title, messages)
    background_tasks.add_task(extract_and_save_memory, message, result["reply"])
    
    return {
        "chat_id": cid,
        "title": title,
        "reply": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    }

@app.delete("/chats/{chat_id}")
async def delete_chat_session(chat_id: str):
    success = await db_helper.delete_chat_session(chat_id)
    if success:
        return {"status": "success", "message": "Chat deleted"}
    raise HTTPException(status_code=404, detail="Chat session not found")

@app.put("/chats/{chat_id}")
async def rename_chat_session(chat_id: str, data: RenameRequest):
    success = await db_helper.rename_chat_session(chat_id, data.title)
    if success:
        return {"status": "success", "message": "Chat renamed", "title": data.title}
    raise HTTPException(status_code=404, detail="Chat session not found")

@app.get("/memory")
async def get_memories():
    facts = await db_helper.get_memories()
    return {"memories": facts}

@app.delete("/memory/{index}")
async def delete_single_memory(index: int):
    facts = await db_helper.get_memories()
    if 0 <= index < len(facts):
        removed = facts.pop(index)
        await db_helper.save_memories(facts)
        return {"status": "success", "message": f"Deleted memory: {removed}"}
    raise HTTPException(status_code=404, detail="Index out of range")

# ==============================================================================
# SECURE EXPOSED API ENDPOINTS FOR RAILWAY BACKEND API & VERCEL INTEGRATION
# ==============================================================================

@app.post("/api/agent/run", dependencies=[Depends(verify_api_token)])
async def run_ide_agent(req: IDEAgentRunRequest):
    """Triggers the high-level autonomous IDE Agent on Railway with the given instruction."""
    try:
        report = await ide_agent.run(req.instruction, req.max_iterations)
        return {"status": "success", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")

@app.post("/api/tools/read_file", dependencies=[Depends(verify_api_token)])
async def api_read_file(req: ReadFileRequest):
    return read_file_tool(req.filepath)

@app.post("/api/tools/patch_file", dependencies=[Depends(verify_api_token)])
async def api_patch_file(req: PatchFileRequest):
    return patch_file_tool(req.filepath, req.search_block, req.replace_block)

@app.post("/api/tools/view_dir", dependencies=[Depends(verify_api_token)])
async def api_view_dir(req: ViewDirRequest):
    return view_dir_tool(req.path)

@app.post("/api/tools/execute_command", dependencies=[Depends(verify_api_token)])
async def api_execute_command(req: ExecuteCommandRequest):
    return execute_command_tool(req.command)

@app.post("/api/tools/clone_repository", dependencies=[Depends(verify_api_token)])
async def api_clone_repository(req: CloneRepoRequest):
    return clone_repository_tool(req.repo_url)

@app.post("/api/tools/git_status", dependencies=[Depends(verify_api_token)])
async def api_git_status():
    return git_status_tool()

@app.post("/api/tools/git_rollback", dependencies=[Depends(verify_api_token)])
async def api_git_rollback():
    return git_rollback_tool()

@app.post("/api/tools/write_file", dependencies=[Depends(verify_api_token)])
async def api_write_file(req: WriteFileRequest):
    return write_file_tool(req.filepath, req.content)

@app.post("/api/tools/list_directory", dependencies=[Depends(verify_api_token)])
async def api_list_directory(req: ListDirectoryRequest):
    return list_directory_tool(req.path)

# ==============================================================================
# WEB-BASED AI IDE ENDPOINTS: FILE UPLOAD & GITHUB IMPORT
# ==============================================================================

@app.post("/api/upload-file")
async def api_upload_file(file: UploadFile = File(...)):
    """Saves an uploaded file directly into the workspace directory."""
    try:
        from agent.tools import clean_path, ensure_workspace
        ws = ensure_workspace()
        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="Filename missing")

        # Clean path to ensure it remains bounded inside workspace
        target_path = clean_path(filename)

        # Ensure target directory hierarchy exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        content = await file.read()
        with open(target_path, "wb") as f:
            f.write(content)

        return {"status": "success", "message": f"Successfully uploaded {filename} to workspace."}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/github/repos")
async def api_github_repos(request: Request):
    """Fetches user repositories from GitHub using a Personal Access Token provided in headers."""
    token = request.headers.get("X-GitHub-Token", "").strip()

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "MyAgent-AI"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        url = "https://api.github.com/user/repos?per_page=100&sort=updated"
    else:
        return {"status": "error", "message": "GitHub Personal Access Token is required."}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                repos = resp.json()
                formatted_repos = [
                    {
                        "name": r.get("name"),
                        "full_name": r.get("full_name"),
                        "clone_url": r.get("clone_url"),
                        "private": r.get("private"),
                        "description": r.get("description")
                    } for r in repos
                ]
                return {"status": "success", "repos": formatted_repos}
            else:
                return {"status": "error", "message": f"GitHub API error: {resp.text}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mcp/config")
async def get_mcp_config_endpoint():
    """Fetches the active MCP configuration from backend."""
    from agent.mcp_loader import load_mcp_config
    return load_mcp_config()

@app.post("/api/mcp/config")
async def save_mcp_config_endpoint(req: MCPConfigRequest):
    """Validates and saves the incoming raw JSON string to mcp_config.json."""
    from agent.mcp_loader import validate_mcp_config, CONFIG_PATH
    validation = validate_mcp_config(req.config_raw)
    if validation["status"] == "error":
        raise HTTPException(status_code=400, detail=validation["message"])

    try:
        # Safe Atomic Write and Replace
        temp_path = CONFIG_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(validation["data"], f, indent=2)
        os.replace(temp_path, CONFIG_PATH)
        return {"status": "success", "message": "MCP configuration saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")

@app.post("/api/github/clone")
async def api_github_clone(req: GitHubCloneRequest):
    """Clones a selected repository into the workspace, supporting authenticated private repositories if token is provided."""
    try:
        from agent.tools import clone_repository_tool
        repo_url = req.repo_url

        if req.token:
            # Inject token into URL for authenticated cloning: https://<token>@github.com/...
            match = re.match(r"https://(github\.com/.*)", repo_url)
            if match:
                repo_url = f"https://{req.token}@{match.group(1)}"

        res = clone_repository_tool(repo_url)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))