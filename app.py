from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agent.agent import chat

app = FastAPI(title="MyAgent")

# -----------------------------
# Static Files
# -----------------------------
app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------------------
# HTML Templates
# -----------------------------
templates = Jinja2Templates(directory="templates")


# -----------------------------
# Home Page
# -----------------------------
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request},
    )


# -----------------------------
# Request Model
# -----------------------------
class ChatRequest(BaseModel):
    message: str


# -----------------------------
# Chat API
# -----------------------------
@app.post("/chat")
async def chat_api(data: ChatRequest):
    try:
        reply = chat(data.message)

        return JSONResponse({
            "reply": reply
        })

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "reply": f"Error: {str(e)}"
            }
        )