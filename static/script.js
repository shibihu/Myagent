const input = document.getElementById("message-input");
const button = document.getElementById("send-button");
const chat = document.getElementById("chat-box");

button.onclick = async function () {

    const text = input.value.trim();

    if (text === "") return;

    // แสดงข้อความของผู้ใช้
    const user = document.createElement("div");
    user.className = "message user";
    user.textContent = text;
    chat.appendChild(user);

    input.value = "";

    // ส่งไป Backend
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

    // แสดงข้อความของ AI
    const ai = document.createElement("div");
    ai.className = "message ai";
    ai.textContent = data.reply;

    chat.appendChild(ai);

    chat.scrollTop = chat.scrollHeight;
};