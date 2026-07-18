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

# === ระบบความจำอัตโนมัติ (Automatic Memory Extraction - FULLY FIXED) ===
async def extract_and_save_memory(user_msg: str, ai_reply: str):
    """ฟังก์ชันทำงานเบื้องหลัง ดักจับและสกัดความจำสำคัญจากบทสนทนาล่าสุดอย่างสมบูรณ์แบบ"""
    memories = load_json_file(MEMORY_FILE)
    
    extraction_prompt = f"""
    วิเคราะห์บทสนทนาล่าสุดด้านล่างนี้ และสกัดข้อมูลสำคัญเกี่ยวกับตัวผู้ใช้เพื่อบันทึกในฐานข้อมูลระยะยาว
    (วิเคราะห์จากหัวข้อคำถาม เช่น ถ้าเขาขอโค้ด Roblox ให้สกัดว่า "ผู้ใช้พัฒนาเกมบน Roblox" หรือถ้าขอสคริปต์ Lua ให้สกัดว่า "ผู้ใช้เขียนสคริปต์ด้วยภาษา Lua" รวมถึงชื่อโปรเจกต์ ฟีเจอร์ หรือสไตล์ดีไซน์ที่เขาเอ่ยถึง)
    
    [บทสนทนา]
    ผู้ใช้: {user_msg}
    AI: {ai_reply}
    
    กฎข้อบังคับในการตอบกลับอย่างเคร่งครัด:
    1. ให้ตอบกลับในรูปแบบ JSON Object โครงสร้างนี้เท่านั้น: {{"memories": ["ข้อความความจำที่ 1", "ข้อความความจำที่ 2"]}}
    2. เขียนข้อความสั้นกระชับ เป็นข้อเท็จจริงระยะยาวเกี่ยวกับผู้ใช้
    3. หากไม่มีข้อมูลพฤติกรรมหรือความชอบใหม่ๆ เลยจริงๆ ให้ตอบกลับด้วยรายการว่างๆ: {{"memories": []}}
    4. ห้ามทักทาย ห้ามมีข้อความเกริ่นนำ ห้ามสรุปปิดท้าย และห้ามใส่เครื่องหมายครอบโค้ด JSON ใดๆ ทั้งสิ้น
    """
    
    try:
        res = await agent.get_response(extraction_prompt)
        raw_reply = res["reply"].strip()
        
        # ใช้ Regular Expression ดักดึงข้อมูลภายใต้เครื่องหมายปีกกาคู่แรกเพื่อแก้ปัญหาโครงสร้างพังร้อยเปอร์เซ็นต์
        match = re.search(r'\{.*\}', raw_reply, re.DOTALL)
        if match:
            json_content = match.group(0)
            parsed = json.loads(json_content)
            new_facts = parsed.get("memories", [])
            
            existing_list = memories.get("facts", [])
            updated = False
            
            for fact in new_facts:
                if fact not in existing_list:
                    existing_list.append(fact)
                    updated = True
                    
            if updated:
                memories["facts"] = existing_list
                save_json_file(MEMORY_FILE, memories)
                print(f"[Memory System Saved]: {new_facts}")
        else:
            print(f"[Memory System Warning]: AI did not return a valid JSON format.")
            
    except Exception as e:
        print(f"[Memory Extraction System Error]: {e}")

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
        
    # ฉีดประวัติความจำดั้งเดิมเข้าไปประกบ System Context เพื่อให้บอทรู้จักเราในทุกคำถาม
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
    
    # ส่งโปรเซสไปวิเคราะห์ความจำเงียบๆ หลังบ้าน โดยไม่หน่วงเวลาส่งคำตอบหน้าจอ
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