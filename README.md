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
├── index.html          # Main chat interface layout
├── README.md           # Project documentation (You are here!)
└── static/
    ├── style.css       # Custom styles for chat layout and bubbles
    └── script.js       # App logic, backend API calls, and Markdown parsing
🛠️ Tech Stack & Dependencies
Frontend: Plain HTML5, CSS3, and Vanilla JavaScript.

Markdown Parsing: marked

Syntax Highlighting: highlight.js

Styling Theme: github-markdown-css

⚙️ How It Works
The user types a message in the input box and clicks Send.

The UI immediately displays the user's text and clears the input.

A POST request is sent to the /chat backend endpoint with the JSON payload:

JSON
{ "message": "User's message here" }
The backend returns a response containing the AI's answer:

JSON
{ "reply": "AI's response in **Markdown** format." }
The frontend parses the Markdown, runs the code syntax highlighter on any embedded code blocks, and appends the message to the screen.

🔧 Prerequisites for Running
To make the chat functional, ensure your backend server (Node.js, Python/Flask, FastAPI, etc.) is up and running, listens on the same host, and handles the /chat route correctly.
