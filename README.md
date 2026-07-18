# 🤖 MyAgent - Minimal AI Chat Interface

A sleek, minimal, and responsive web-based chat interface designed for interacting with an AI backend. It features real-time Markdown rendering and automatic code syntax highlighting to look exactly like GitHub's clean documentation style.

## 🚀 Features

*   **Real-time Chat UI:** Clean and simple message-bubble interface for both user and AI.
*   **Markdown Support:** Uses `marked.js` to render headings, lists, bold text, and tables seamlessly.
*   **Syntax Highlighting:** Integrated with `highlight.js` (GitHub Dark theme) to format code blocks beautifully.
*   **GitHub Markdown Styling:** Wrapped in `github-markdown-css` for a polished, modern developer feel.
*   **Auto-Scroll:** Automatically scrolls down to the newest message whenever the user or AI speaks.

## 📂 Project Structure

```text
├── app.py              # FastAPI application entry point
├── config.py           # Environment loading
├── agent/              # Chat agent logic
├── static/             # CSS and JavaScript assets
├── templates/          # HTML templates
├── requirements.txt    # Python dependencies
└── .devcontainer/      # Codespaces / VS Code dev container config
```

## ▶️ Run locally

```bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Then open http://127.0.0.1:8000/.

## ☁️ Run in GitHub Codespaces or VS Code

1. Open the project in Codespaces or VS Code.
2. If prompted, reopen in the dev container.
3. Run:

```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## 🔐 Groq API setup

Create a file named `.env` in the project root with:

```env
GROQ_API_KEY=your_groq_api_key_here
```

If the key is missing, the app will still start and return a friendly message instead of crashing.
