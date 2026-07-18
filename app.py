import os
import uuid
import json
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agent import ChatAgent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "chats.json")
MEMORY_FILE = os.path.join(BASE_DIR, "memory.json")

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

# === ระบบความจำอัตโนมัติ (Automatic Memory Extraction) ===
async def extract_and_save_memory(user_msg: str, ai_reply: str):
    """ฟังก์ชันทำงานเบื้องหลัง สกัดความจำสำคัญจากบทสนทนาล่าสุด"""
    memories = load_json_file(MEMORY_FILE)
    
    # ส่ง Prompt พิเศษไปถาม AI เพื่อสกัดข้อเท็จจริงสั้นๆ เกี่ยวกับตัวผู้ใช้
    extraction_prompt = f"""
    วิเคราะห์บทสนทนาล่าสุดด้านล่างนี้ และสกัดข้อมูลสำคัญเกี่ยวกับตัวผู้ใช้ (เช่น ชื่อโปรเจกต์, เกมที่พัฒนา, ภาษาโปรแกรมที่ใช้, สไตล์ดีไซน์ที่ชอบ, ข้อจำกัด, หรือความชอบส่วนตัว)
    
    [บทสนทนา]
    ผู้ใช้: {user_msg}
    AI: {ai_reply}
    
    กฎการตอบกลับ:
    1. ตอบกลับมาในรูปแบบ JSON Object ที่มี Key ชื่อ "memories" และเป็น Array ของ String เท่านั้น เช่น {{"memories": ["ผู้ใช้กำลังพัฒนาเกมชื่อ Cookie Yummy", "ชอบใช้ดีไซน์ UI สไตล์ดาร์กโทน"]}}
    2. สกัดเอาเฉพาะข้อเท็จจริงที่ชัดเจนและเป็นประโยชน์ระยะยาว ห้ามเดาหรือสรุปมั่ว
    3. หากไม่มีข้อมูลใหม่ที่สำคัญ ให้ตอบกลับด้วยรายการว่างๆ: {{"memories": []}}
    4. ห้ามมีข้อความเกริ่นนำหรือคำอธิบายใดๆ นอกเหนือจาก JSON เด็ดขาด!
    """
    
    try:
        # เรียกใช้โมเดลผ่าน agent (แนะนำให้ใช้โมเดลตัวเล็กและเร็วอย่าง llama3-8b เพื่อประหยัดเวลาและ token)
        res = await agent.get_response(extraction_prompt)
        raw_reply = res["reply"].strip()
        
        # ตัดตัวครอบโค้ดออกหาก AI แอบใส่มา
        if raw_reply.startswith("```json"):
            raw_reply = raw_reply.split("```json")[1].split("```")[0].strip()
        elif raw_reply.startswith("```"):
            raw_reply = raw_reply.split("```")[1].split("```")[0].strip()
            
        parsed = json.loads(raw_reply)
        new_facts = parsed.get("memories", [])
        
        # นำความจำใหม่มาบันทึกผสมกับความจำเดิม (ป้องกันการบันทึกซ้ำ)
        existing_list = memories.get("facts", [])
        updated = False
        
        for fact in new_facts:
            if fact not in existing_list:
                existing_list.append(fact)
                updated = True
                
        if updated:
            memories["facts"] = existing_list
            save_json_file(MEMORY_FILE, memories)
            
    except Exception as e:
        print(f"[Memory Extraction Error]: {e}")

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
        
    # --- ฉีดความจำเก่าเข้าไปในระบบเพื่อให้ AI รู้จักเราอยู่ตลอดเวลา ---
    injected_message = data.message
    facts = memories.get("facts", [])
    if facts:
        memory_context = "\n".join([f"- {f}" for f in facts])
        # ฝังข้อมูลไว้ด้านหน้าคำสั่งหลักเพื่อให้บอทระลึกถึงบริบทของตัวเราได้ทันที
        injected_message = f"[ข้อมูลความจำเกี่ยวกับผู้ใช้ที่คุณบันทึกไว้คราวก่อน:\n{memory_context}]\n\nคำสั่ง/คำถามปัจจุบัน: {data.message}"

    chat_sessions[cid]["messages"].append({
        "role": "user", 
        "content": data.message, # เก็บข้อความจริงที่ผู้ใช้พิมพ์ลงประวัติแชทปกติ
        "model": None,
        "total_tokens": 0
    })
    
    # ยิงส่งคำถามพร้อมร่างประวัติความจำจำแลงเข้าไปในระบบประมวลผล
    result = await agent.get_response(injected_message)
    
    chat_sessions[cid]["messages"].append({
        "role": "ai", 
        "content": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    })
    
    save_json_file(DATA_FILE, chat_sessions)
    
    # เรียกกระบวนการหลังบ้าน (Background Task) แอบดักจับและเรียนรู้ความจำอัตโนมัติ โดยไม่ส่งผลให้ผู้ใช้ต้องรอนาน
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

# --- Endpoints ใหม่สำหรับจัดการระบบความจำตรงหน้า UI ---
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