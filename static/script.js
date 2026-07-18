const input = document.getElementById("message-input");
const button = document.getElementById("send-button");
const chat = document.getElementById("chat-box");

button.onclick = async function () {

    const text = input.value.trim();

    if (text === "") return;

    // แสดงข้อความของผู้ใช้ (Show user message)
    const user = document.createElement("div");
    user.className = "message user";
    user.textContent = text;
    chat.appendChild(user);

    input.value = "";

    // ส่งไป Backend (Send to backend)
    const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message: text
        })
    });

    const data = await response.json();

    // แสดงข้อความของ AI (Show AI message)
    const ai = document.createElement("div");
    
    // FIX 1: Added 'markdown-body' class so the GitHub Markdown CSS works
    ai.className = "message ai markdown-body"; 
    
    // FIX 2: Changed 'aiMessage.innerHTML' to 'ai.innerHTML' (aiMessage was undefined)
    ai.innerHTML = marked.parse(data.reply);

    // FIX 3: Scope the syntax highlighter to *only* look inside the new AI message 
    // Instead of re-scanning the entire page every time
    ai.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
    });

    chat.appendChild(ai);

    // เลื่อนหน้าจอลงล่างสุด (Scroll to bottom)
    chat.scrollTop = chat.scrollHeight;
};
