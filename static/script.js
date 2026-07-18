const input = document.getElementById("message-input");
const button = document.getElementById("send-button");
const chatBox = document.getElementById("chat-box");
const historyList = document.getElementById("history-list");
const newChatBtn = document.getElementById("new-chat-btn");
const toggleSidebarBtn = document.getElementById("toggle-sidebar-btn");
const sidebar = document.getElementById("sidebar");
const chatTitle = document.getElementById("chat-title");

let currentChatId = null;

// ควบคุมเปิด/ปิด Sidebar
toggleSidebarBtn.onclick = () => {
    sidebar.classList.toggle("closed");
};

// คลิกพื้นที่แชทเพื่อปิด sidebar อัตโนมัติ (อำนวยความสะดวกบนมือถือ)
chatBox.onclick = () => {
    if (window.innerWidth <= 768) {
        sidebar.classList.add("closed");
    }
};

// ฟังก์ชันสำหรับเรนเดอร์ข้อความและสร้างปุ่ม Copy Code
function renderMessage(role, content, model = null, tokens = 0) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role === "user" ? "user" : "ai markdown-body"}`;
    
    if (role === "user") {
        msgDiv.textContent = content;
    } else {
        msgDiv.innerHTML = marked.parse(content);
        
        // ใส่กล่องรายละเอียดโมเดลและ Token
        if (model) {
            const tokenBadge = document.createElement("div");
            tokenBadge.style.cssText = "font-size:11px; color:#8b949e; margin-top:10px; border-top:1px solid #30363d; padding-top:6px; display:inline-block; font-family:monospace;";
            tokenBadge.textContent = `🧠 Model: ${model} | 📊 Tokens Used: ${tokens}`;
            msgDiv.appendChild(tokenBadge);
        }

        // --- เพิ่มปุ่ม Copy Code ให้กับโค้ดบล็อกทุกตัว ---
        msgDiv.querySelectorAll("pre").forEach((preBlock) => {
            const codeBlock = preBlock.querySelector("code");
            if (!codeBlock) return;

            // สร้างปุ่มคัดลอก
            const copyBtn = document.createElement("button");
            copyBtn.className = "copy-code-btn";
            copyBtn.textContent = "📋 Copy";

            // ฟังก์ชันตอนกดปุ่มคัดลอก
            copyBtn.onclick = async () => {
                try {
                    await navigator.clipboard.writeText(codeBlock.innerText);
                    copyBtn.textContent = "✅ Copied!";
                    copyBtn.style.backgroundColor = "#238636";
                    
                    // เปลี่ยนคำกลับเป็นเหมือนเดิมหลังผ่านไป 2 วินาที
                    setTimeout(() => {
                        copyBtn.textContent = "📋 Copy";
                        copyBtn.style.backgroundColor = "#21262d";
                    }, 2000);
                } catch (err) {
                    console.error("Failed to copy text: ", err);
                }
            };

            preBlock.appendChild(copyBtn);
        });
    }

    // ทำ Syntax Highlighting
    msgDiv.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
    });

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ดึงรายการแชททั้งหมดมาโชว์ที่ Sidebar
async function loadChatHistoryList() {
    try {
        const res = await fetch("/chats");
        const list = await res.json();
        historyList.innerHTML = "";
        
        list.forEach(item => {
            const li = document.createElement("li");
            li.className = `history-item ${item.id === currentChatId ? 'active' : ''}`;
            li.textContent = item.title;
            li.onclick = () => {
                switchChatSession(item.id);
                if (window.innerWidth <= 768) sidebar.classList.add("closed"); // ปิดแถบข้างเมื่อกดเลือกบนมือถือ
            };
            historyList.appendChild(li);
        });
    } catch (err) {
        console.error("Error loading history list:", err);
    }
}

// สลับห้องแชท
async function switchChatSession(chatId) {
    currentChatId = chatId;
    chatBox.innerHTML = "";
    
    try {
        const res = await fetch(`/chats/${chatId}`);
        const data = await res.json();
        chatTitle.textContent = `MyAgent - ${data.title}`;
        
        data.messages.forEach(msg => {
            renderMessage(msg.role, msg.content, msg.model, msg.total_tokens);
        });
        
        loadChatHistoryList();
    } catch (err) {
        console.error("Error loading chat context:", err);
    }
}

// ปุ่มสร้าง New Chat
newChatBtn.onclick = () => {
    currentChatId = null;
    chatBox.innerHTML = "";
    chatTitle.textContent = "MyAgent - New Chat";
    loadChatHistoryList();
    if (window.innerWidth <= 768) sidebar.classList.add("closed"); // ปิดแถบข้างหลังกดสร้างบนมือถือ
};

// ส่งข้อความคุย
async function sendMessage() {
    const text = input.value.trim();
    if (text === "") return;

    renderMessage("user", text);
    input.value = "";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                message: text,
                chat_id: currentChatId
            })
        });

        const data = await response.json();
        currentChatId = data.chat_id;
        chatTitle.textContent = `MyAgent - ${data.title}`;

        renderMessage("ai", data.reply, data.model, data.total_tokens);
        loadChatHistoryList();
    } catch (error) {
        renderMessage("ai", "⚠️ Could not sync transaction data upstream with the network server.");
    }
}

button.onclick = sendMessage;
input.onkeydown = function (e) {
    if (e.key === "Enter") {
        sendMessage();
    }
};

// โหลดข้อมูลครั้งแรก
loadChatHistoryList();
