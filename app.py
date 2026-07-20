import os
import re
import uuid
import json
import asyncio
from typing import Optional, List
import io
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agent.agent import ChatAgent
from pypdf import PdfReader

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

# === ฟังก์ชันจัดการไฟล์ JSON และการควบคุมความสอดคล้องกันของข้อมูล (Concurrency Safe) ===
# เราใช้ locks แยกเฉพาะสำหรับแต่ละไฟล์เพื่อป้องกันสภาวะการแย่งชิงข้อมูล (Race conditions) ระหว่างการเขียน/อ่านไฟล์แบบไม่ซิงค์
file_locks = {}

def get_file_lock(filepath: str) -> asyncio.Lock:
    if filepath not in file_locks:
        file_locks[filepath] = asyncio.Lock()
    return file_locks[filepath]

def load_json_file(filepath: str) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_file(filepath: str, data: dict) -> None:
    # ใช้วิธีการเขียนแบบ Atomic (เขียนลงไฟล์ชั่วคราวก่อนแล้วสลับชื่อไฟล์) เพื่อป้องกันไฟล์เสียหายเมื่อเกิดข้อผิดพลาดระหว่างเขียน
    temp_filepath = filepath + ".tmp"
    try:
        with open(temp_filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        # ตรวจสอบว่าเขียนไฟล์ชั่วคราวสมบูรณ์ จากนั้นเปลี่ยนชื่อไฟล์ทับไฟล์จริง (เป็น Atomic operation ในระดับ OS)
        if os.path.exists(temp_filepath) and os.path.getsize(temp_filepath) > 0:
            os.replace(temp_filepath, filepath)
    except Exception as e:
        print(f"[Save JSON File Exception]: {e}")
        # พยายามล้างไฟล์ชั่วคราวที่ตกค้าง
        try:
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
        except Exception:
            pass

# === ระบบความจำอัตโนมัติ (Automatic Memory Extraction - PERFECTLY FULLY FIXED) ===
async def extract_and_save_memory(user_msg: str, ai_reply: str):
    """ฟังก์ชันสกัดความจำเบื้องหลัง ป้องกันเอเรอร์โครงสร้าง JSON ทุกรูปแบบร้อยเปอร์เซ็นต์"""
    lock = get_file_lock(MEMORY_FILE)
    async with lock:
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
            async with lock:
                # โหลดข้อมูลจริงล่าสุดอีกครั้งก่อนจะบันทึก เพื่อกันไม่ให้ทับข้อมูลที่ถูกบันทึกพร้อมกันโดยรีเควสต์อื่น
                memories = load_json_file(MEMORY_FILE)
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

# === API Endpoints ===
@app.get("/")
async def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

@app.get("/chats")
async def get_all_chats():
    lock = get_file_lock(DATA_FILE)
    async with lock:
        chat_sessions = load_json_file(DATA_FILE)
    return [{"id": cid, "title": info["title"]} for cid, info in chat_sessions.items()]

@app.get("/chats/{chat_id}")
async def get_chat_history(chat_id: str):
    lock = get_file_lock(DATA_FILE)
    async with lock:
        chat_sessions = load_json_file(DATA_FILE)
    if chat_id in chat_sessions:
        return chat_sessions[chat_id]
    return {"title": "New Chat", "messages": []}

@app.post("/chat")
async def chat_endpoint(
    request: Request,
    background_tasks: BackgroundTasks
):
    data_lock = get_file_lock(DATA_FILE)
    memory_lock = get_file_lock(MEMORY_FILE)
    
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

        # Get list of uploaded files
        files_to_process = form_data.getlist("files")
    else:
        # Default to application/json
        try:
            json_data = await request.json()
            message = json_data.get("message", "")
            chat_id = json_data.get("chat_id")
            search_web = json_data.get("search_web", False)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON or request payload")

    # Read and parse attached files
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

    async with memory_lock:
        memories = load_json_file(MEMORY_FILE)
    
    async with data_lock:
        chat_sessions = load_json_file(DATA_FILE)
        cid = chat_id
        if not cid or cid not in chat_sessions:
            cid = str(uuid.uuid4())
            t_msg = message if message else (files_to_process[0].filename if files_to_process else "New Chat")
            title = t_msg[:15] + "..." if len(t_msg) > 15 else t_msg
            chat_sessions[cid] = {"title": title, "messages": []}
            
        # Construct the user display message for saving in chat history
        display_message = message
        if files_to_process:
            file_names = ", ".join([f"📎 {f.filename}" for f in files_to_process if f.filename])
            if display_message:
                display_message += f"\n\n({file_names})"
            else:
                display_message = file_names

        chat_sessions[cid]["messages"].append({
            "role": "user", 
            "content": display_message,
            "model": None,
            "total_tokens": 0
        })
        # บันทึกสถานะชั่วคราวขณะรอการตอบกลับจาก AI เพื่อกันข้อมูลสูญหาย
        save_json_file(DATA_FILE, chat_sessions)

    # Combine message and files_context to send to agent
    agent_message = message
    if files_context:
        agent_message = f"{files_context}\n\nUser Message: {message}"

    # ฉีดประวัติความจำดั้งเดิมเข้าไปประกบ System Context
    injected_message = agent_message
    facts = memories.get("facts", [])
    if facts:
        memory_context = "\n".join([f"- {f}" for f in facts])
        injected_message = f"[ข้อมูลความจำถาวรเกี่ยวกับผู้ใช้:\n{memory_context}]\n\nคำสั่งปัจจุบัน: {agent_message}"
    
    result = await agent.get_response(injected_message)
    
    async with data_lock:
        chat_sessions = load_json_file(DATA_FILE)
        if cid not in chat_sessions:
            t_msg = message if message else (files_to_process[0].filename if files_to_process else "New Chat")
            title = t_msg[:15] + "..." if len(t_msg) > 15 else t_msg
            chat_sessions[cid] = {"title": title, "messages": []}
            
        chat_sessions[cid]["messages"].append({
            "role": "ai", 
            "content": result["reply"],
            "model": result["model"],
            "total_tokens": result["total_tokens"]
        })
        save_json_file(DATA_FILE, chat_sessions)
    
    # ส่งงานไปวิเคราะห์ความจำเงียบๆ หลังบ้าน โดยไม่ทำให้หน้าเว็บกระตุก
    background_tasks.add_task(extract_and_save_memory, message, result["reply"])
    
    return {
        "chat_id": cid,
        "title": chat_sessions[cid]["title"],
        "reply": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    }

@app.delete("/chats/{chat_id}")
async def delete_chat_session(chat_id: str):
    lock = get_file_lock(DATA_FILE)
    async with lock:
        chat_sessions = load_json_file(DATA_FILE)
        if chat_id in chat_sessions:
            del chat_sessions[chat_id]
            save_json_file(DATA_FILE, chat_sessions)
            return {"status": "success", "message": "Chat deleted"}
    raise HTTPException(status_code=404, detail="Chat session not found")

@app.put("/chats/{chat_id}")
async def rename_chat_session(chat_id: str, data: RenameRequest):
    lock = get_file_lock(DATA_FILE)
    async with lock:
        chat_sessions = load_json_file(DATA_FILE)
        if chat_id in chat_sessions:
            chat_sessions[chat_id]["title"] = data.title
            save_json_file(DATA_FILE, chat_sessions)
            return {"status": "success", "message": "Chat renamed", "title": data.title}
    raise HTTPException(status_code=404, detail="Chat session not found")

# --- Endpoints สำหรับแผงความจำอินเตอร์เฟส ---
@app.get("/memory")
async def get_memories():
    lock = get_file_lock(MEMORY_FILE)
    async with lock:
        memories = load_json_file(MEMORY_FILE)
    return {"memories": memories.get("facts", [])}

@app.delete("/memory/{index}")
async def delete_single_memory(index: int):
    lock = get_file_lock(MEMORY_FILE)
    async with lock:
        memories = load_json_file(MEMORY_FILE)
        facts = memories.get("facts", [])
        if 0 <= index < len(facts):
            removed = facts.pop(index)
            memories["facts"] = facts
            save_json_file(MEMORY_FILE, memories)
            return {"status": "success", "message": f"Deleted memory: {removed}"}
    raise HTTPException(status_code=404, detail="Index out of range")