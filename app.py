from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="MyAgent")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request},
    )


# -----------------------
# Chat API
# -----------------------

class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
async def chat(data: ChatRequest):

    return JSONResponse({
        "reply": f"You said: {data.message}"
    })