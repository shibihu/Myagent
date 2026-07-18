import os
import uuid
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agent.agent import ChatAgent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

agent = ChatAgent()

# โครงสร้างเก็บข้อมูลแชทในหน่วยความจำ
# รูปแบบ: { chat_id: { "title": "ชื่อแชท", "messages": [ {role, content, model, tokens}... ] } }
chat_sessions = {}

class ChatRequest(BaseModel):
    message: str
    chat_id: str = None

@app.get("/")
async def index_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})

# 1. Endpoint ดึงรายการแชททั้งหมดไปโชว์ที่ Sidebar
@app.get("/chats")
async def get_all_chats():
    return [{"id": cid, "title": info["title"]} for cid, info in chat_sessions.items()]

# 2. Endpoint ดึงประวัติข้อความของแชทเฉพาะห้อง
@app.get("/chats/{chat_id}")
async def get_chat_history(chat_id: str):
    if chat_id in chat_sessions:
        return chat_sessions[chat_id]
    return {"title": "New Chat", "messages": []}

# 3. Endpoint ส่งข้อความคุยและบันทึกลงประวัติ
@app.post("/chat")
async def chat_endpoint(data: ChatRequest):
    cid = data.chat_id
    
    # ถ้าไม่มี chat_id ส่งมา หรือไม่มีในระบบ ให้สร้างห้องใหม่
    if not cid or cid not in chat_sessions:
        cid = str(uuid.uuid4())
        # ใช้ 15 ตัวแรกของข้อความเป็นชื่อหัวข้อแชทชั่วคราว
        title = data.message[:15] + "..." if len(data.message) > 15 else data.message
        chat_sessions[cid] = {"title": title, "messages": []}
        
    # บันทึกข้อความฝั่ง User
    chat_sessions[cid]["messages"].append({
        "role": "user", 
        "content": data.message,
        "model": None,
        "total_tokens": 0
    })
    
    # เรียกบอทคุย
    result = await agent.get_response(data.message)
    
    # บันทึกข้อความฝั่ง AI
    chat_sessions[cid]["messages"].append({
        "role": "ai", 
        "content": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    })
    
    return {
        "chat_id": cid,
        "title": chat_sessions[cid]["title"],
        "reply": result["reply"],
        "model": result["model"],
        "total_tokens": result["total_tokens"]
    }
