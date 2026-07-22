# 🤖 MyAgent — Web-Based AI IDE & Autonomous Code Agent
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org) [![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com) [![Vercel](https://img.shields.io/badge/Frontend-Vercel-black?logo=vercel)](https://vercel.com) [![Railway](https://img.shields.io/badge/Backend-Railway-purple?logo=railway)](https://railway.app)
> **MyAgent** is an intelligent, full-stack Web AI IDE designed to execute real code operations, manage files in workspaces, stream real-time execution status, and sync directly with GitHub repositories.
---
## 🔥 Key Features
| Feature | Description |
| :--- | :--- |
| **🐊 GitHub Integration** | Import repositories via OAuth, execute `git clone`, `commit`, and `push` directly from chat. |
| **💾 Workspace File Engine** | Read, write, edit, delete, and inspect files/directories live on the backend server. |
| **⚡ Real-time Thought Stream** | Live workflow status updates (`Git cloning...`, `Updating code...`, `Running script...`). |
| **💻 Attachment & Import** | Dedicated UI pop-up for direct file uploads and GitHub repository importing. |
| **📝 Persistent Chat State** | Client-side session management powered by `localStorage` for uninterrupted chats. |
| **✈️ Multi-Model Engine** | Powered by Gemini & Groq LLMs with smart tool calling & token optimization. |
---
## 🐍 Tech Stack & Architecture
* **Frontend:** Next.js / React (Hosted on Vercel)
* **Backend:** Python FastAPI / Uvicorn (Hosted on Railway)
* **Tooling Engine:** Custom Subprocess Git Automation & File Management Tools
* **LLM Models:** Google Gemini 2.5 Flash / Groq (Llama 3.3 70B)
---
## ✈️ Quick Start (Local Setup)
1. **Clone the repository:**
```bash
 git clone [https://github.com/shibihu/Myagent.git](https://github.com/shibihu/Myagent.git)
 cd Myagent
```
