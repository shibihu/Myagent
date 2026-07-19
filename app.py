import os
import re
import uuid
import json
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agent.agent import ChatAgent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_file_path(filename: str) -> str:
    # If running on Vercel or AWS Lambda, always use /tmp
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return os.path.join("/tmp", filename)

    # Try writing to the local folder; if that fails or is read-only, fallback to /tmp
    local_path = os.path.join(BASE_DIR, filename)
    try:
        test_path = local_path + ".test"
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(test_path)
        return local_path
    except Exception:
        return os.path.join("/tmp", filename)

DATA_FILE = get_file_path("chats.json")
MEMORY_FILE = get_file_path("memory.json")

app = FastAPI()

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

agent = ChatAgent()

# === ฟังก์ชันจัดการไฟล์ JSON ===
def load_json_file(filepath: str) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_file(filepath: str, data: dict) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# === ระบบความจำอัตโนมัติ (Automatic Memory Extraction - PERFECTLY FULLY FIXED) ===
async def extract_and_save_memory(user_msg: str, ai_reply: str):
    """ฟังก์ชันสกัดความจำเบื้องหลัง ป้องกันเอเรอร์โครงสร้าง JSON ทุกรูปแบบร้อยเปอร์เซ็นต์"""
    memories = load_json_file(MEMORY_FILE)
    
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
        
        # ค้นหาข้อความรูปแบบ JSON ที่แท้จริง (มองหาตัวที่เปิดด้วย {"memories")
        match = re.search(r'\{\s*["\']memories["\']\s*:\s*\[.*\]\s*\}', raw_reply, re.DOTALL)
        
        if match:
            json_content = match.group(0)
            # แก้ไขสัญกรณ์ Single Quote หลุดกรอบให้กลายเป็น Double Quote ตามมาตรฐาน JSON
            json_content = re.sub(r"'\s*,\s*'", '", "', json_content)
            json_content = re.sub(r"\[\s*'", '["', json_content)
            json_content = re.sub(r"'\s*\]", '"]', json_content)
            
            try:
                parsed = json.loads(json_content)
                new_facts = parsed.get("memories", [])
            except json.JSONDecodeError:
                # Fallback Step 1: ถ้า json.loads ยังบ่นเรื่องโควท แงะสดด้วย Regex เลย
                new_facts = re.findall(r'["\'](.*?)["\']', json_content)
                new_facts = [f for f in new_facts if f != "memories"]
        else:
            # Fallback Step 2: ในกรณีที่ AI ไม่ส่งโครงสร้าง JSON มาเลย แต่เขียนมาเป็น List
            # ดักจับข้อความใดๆ ที่อยู่ในเครื่องหมายอัญประกาศคู่หรือเดี่ยว
            lines = re.findall(r'["\'](.*?)["\']', raw_reply)
            new_facts = [l.strip() for l in lines if l.strip() and l != "memories" and len(l) > 3]

        # ทำการบันทึกเมื่อดึงข้อเท็จจริงออกมาสำเร็จ
        if new_facts:
            existing_list = memories.get("facts", [])
            updated = False
            
            for fact in new_facts:
                # ป้องกันการบันทึกคำว่า memories เข้าไปตรงๆ และเช็กไม่ให้ซ้ำ
                if fact not in existing_list and fact.lower() != "memories":
                    existing_list.append(fact)
                    updated = True
                    
            if updated:
                memories["facts"] = existing_list
                save_json_file(MEMORY_FILE, memories)
                print(f"[Memory System Block Saved]: {new_facts}")
                
    except Exception as e:
        print(f"[Memory Extraction Fatal Overruled Exception]: {e}")

# === Pydantic Models ===
class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None

class RenameRequest(BaseModel):
    title: str

class CommandRequest(BaseModel):
    command: str

class GitPushRequest(BaseModel):
    commit_message: str

class MCPRequest(BaseModel):
    provider: str
    active: bool
    token: Optional[str] = None

# === API Endpoints ===
import subprocess

def is_localhost_request(request: Request) -> bool:
    """Checks if the request is originating from localhost."""
    client_host = request.client.host if request.client else None
    return client_host in ("127.0.0.1", "::1", "localhost")

@app.post("/ide/run")
async def run_terminal_command(data: CommandRequest, request: Request):
    if not is_localhost_request(request):
        raise HTTPException(
            status_code=403,
            detail="❌ Access Denied: Executing terminal commands is restricted to localhost for security."
        )

    cmd = data.command.strip()
    if not cmd:
        return {"output": ""}

    forbidden_tokens = ["rm -rf /", "sudo", "mv /", "mkfs", "dd"]
    if any(token in cmd for token in forbidden_tokens):
        return {"output": "❌ Access Denied: This command is forbidden for security reasons."}

    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
        return {"output": output if output else "Command completed with no standard output."}
    except Exception as e:
        return {"output": f"Error: {e}"}

@app.post("/ide/git-push")
async def git_push_workspace(data: GitPushRequest, request: Request):
    if not is_localhost_request(request):
        raise HTTPException(
            status_code=403,
            detail="❌ Access Denied: Git operations are restricted to localhost for security."
        )

    msg = data.commit_message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="Commit message is required")

    try:
        commands = [
            ["git", "add", "."],
            ["git", "commit", "-m", msg],
            ["git", "push", "origin", "main"]
        ]

        outputs = []
        for cmd in commands:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            outputs.append(f"$ {' '.join(cmd)}\nStdout: {res.stdout}\nStderr: {res.stderr}\n")

        return {"status": "success", "message": "\n".join(outputs)}
    except Exception as e:
        return {"status": "error", "message": f"Git pushing failed: {e}"}

mcp_states = {}
import httpx

@app.post("/ide/mcp")
async def mcp_connection_manager(data: MCPRequest):
    if not data.active:
        mcp_states[data.provider] = False
        return {"status": "success", "provider": data.provider, "active": False}

    token = data.token.strip() if data.token else ""
    if not token:
        raise HTTPException(status_code=400, detail="API Token/Key is required to connect!")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if data.provider == "github":
                # Validate GitHub Personal Access Token (PAT)
                res = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"token {token}"}
                )
                if res.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Invalid GitHub Token (Status {res.status_code}): {res.text}")

            elif data.provider == "render":
                # Validate Render API Key
                res = await client.get(
                    "https://api.render.com/v1/services",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if res.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Invalid Render Token (Status {res.status_code}): {res.text}")

            elif data.provider == "roblox":
                # Roblox OpenCloud key validation or syntax check
                if len(token) < 20:
                    raise HTTPException(status_code=400, detail="Invalid Roblox OpenCloud Key format.")

            else:
                raise HTTPException(status_code=400, detail="Unknown provider")

        mcp_states[data.provider] = True
        return {"status": "success", "provider": data.provider, "active": True, "message": "Successfully validated and connected!"}

    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Network error trying to connect to provider: {e}")

@app.get("/")
async def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/chats")
async def get_all_chats():
    chat_sessions = load_json_file(DATA_FILE)
    return [{"id": cid, "title": info["title"]} for cid, info in chat_sessions.items()]

@app.get("/chats/{chat_id}")
async def get_chat_history(chat_id: str):
    chat_sessions = load_json_file(DATA_FILE)
    if chat_id in chat_sessions:
        return chat_sessions[chat_id]
    return {"title": "New Chat", "messages": []}

@app.post("/chat")
async def chat_endpoint(data: ChatRequest, background_tasks: BackgroundTasks):
    chat_sessions = load_json_file(DATA_FILE)
    memories = load_json_file(MEMORY_FILE)
    
    cid = data.chat_id
    if not cid or cid not in chat_sessions:
        cid = str(uuid.uuid4())
        title = data.message[:15] + "..." if len(data.message) > 15 else data.message
        chat_sessions[cid] = {"title": title, "messages": []}
        
    # ฉีดประวัติความจำดั้งเดิมเข้าไปประกบ System Context
    injected_message = data.message
    facts = memories.get("facts", [])
    if facts:
        memory_context = "\n".join([f"- {f}" for f in facts])
        injected_message = f"[ข้อมูลความจำถาวรเกี่ยวกับผู้ใช้:\n{memory_context}]\n\nคำสั่งปัจจุบัน: {data.message}"

    chat_sessions[cid]["messages"].append({
        "role": "user", 
        "content": data.message, 
        "model": None,
        "total_tokens": 0
    })
    
    result = await agent.get_response(injected_message)
    
    chat_sessions[cid]["messages"].append({
        "role": "ai", 
        "content": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    })
    
    save_json_file(DATA_FILE, chat_sessions)
    
    # ส่งงานไปวิเคราะห์ความจำเงียบๆ หลังบ้าน โดยไม่ทำให้หน้าเว็บกระตุก
    background_tasks.add_task(extract_and_save_memory, data.message, result["reply"])
    
    return {
        "chat_id": cid,
        "title": chat_sessions[cid]["title"],
        "reply": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    }

@app.delete("/chats/{chat_id}")
async def delete_chat_session(chat_id: str):
    chat_sessions = load_json_file(DATA_FILE)
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
        save_json_file(DATA_FILE, chat_sessions)
        return {"status": "success", "message": "Chat deleted"}
    raise HTTPException(status_code=404, detail="Chat session not found")

@app.put("/chats/{chat_id}")
async def rename_chat_session(chat_id: str, data: RenameRequest):
    chat_sessions = load_json_file(DATA_FILE)
    if chat_id in chat_sessions:
        chat_sessions[chat_id]["title"] = data.title
        save_json_file(DATA_FILE, chat_sessions)
        return {"status": "success", "message": "Chat renamed", "title": data.title}
    raise HTTPException(status_code=404, detail="Chat session not found")

# --- Endpoints สำหรับแผงความจำอินเตอร์เฟส ---
@app.get("/memory")
async def get_memories():
    memories = load_json_file(MEMORY_FILE)
    return {"memories": memories.get("facts", [])}

@app.delete("/memory/{index}")
async def delete_single_memory(index: int):
    memories = load_json_file(MEMORY_FILE)
    facts = memories.get("facts", [])
    if 0 <= index < len(facts):
        removed = facts.pop(index)
        memories["facts"] = facts
        save_json_file(MEMORY_FILE, memories)
        return {"status": "success", "message": f"Deleted memory: {removed}"}
    raise HTTPException(status_code=404, detail="Index out of range")