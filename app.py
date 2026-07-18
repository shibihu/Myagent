import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from agent.agent import ChatAgent

# Get the directory where app.py lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI()

# Mount layout assets and templates using dynamic paths
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Initialize Agent
agent = ChatAgent()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
async def index_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat_endpoint(data: ChatRequest):
    reply = await agent.get_response(data.message)
    return {"reply": reply}