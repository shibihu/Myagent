const input = document.getElementById("message-input");
const button = document.getElementById("send-button");
const chatBox = document.getElementById("chat-box");
const historyList = document.getElementById("history-list");
const newChatBtn = document.getElementById("new-chat-btn");
const toggleSidebarBtn = document.getElementById("toggle-sidebar-btn");
const sidebar = document.getElementById("sidebar");
const chatTitle = document.getElementById("chat-title");

let currentChatId = null; // คุมไว้ว่าตอนนี้อยู่ห้องแชทไหน (null = ห้องใหม่)

// --- 1. ควบคุมการเปิด/ปิด Sidebar ---
toggleSidebarBtn.onclick = () => {
    sidebar.classList.toggle("closed");
};

// --- 2. ฟังก์ชันช่วยสร้างกล่องข้อความบนหน้าจอ ---
function renderMessage(role, content, model = null, tokens = 0) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role === "user" ? "user" : "ai markdown-body"}`;
    
    if (role === "user") {
        msgDiv.textContent = content;
    } else {
        msgDiv.innerHTML = marked.parse(content);
        
        // ถ้าเป็นข้อความบอท ให้แถมกล่อง Tokens สไตล์เดิมที่คุณชอบ
        if (model) {
            const tokenBadge = document.createElement("div");
            tokenBadge.style.cssText = "font-size:11px; color:#8b949e; margin-top:10px; border-top:1px solid #30363d; padding-top:6px; display:inline-block; font-family:monospace;";
            tokenBadge.textContent = `🧠 Model: ${model} | 📊 Tokens Used: ${tokens}`;
            msgDiv.appendChild(tokenBadge);
        }
    }

    // ไฮไลต์โค้ด
    msgDiv.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
    });

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// --- 3. ดึงรายการแชททั้งหมดมาโชว์ที่ Sidebar ---
async function loadChatHistoryList() {
    try {
        const res = await fetch("/chats");
        const list = await res.json();
        historyList.innerHTML = ""; // ล้างค่าเก่า
        
        list.forEach(item => {
            const li = document.createElement("li");
            li.className = `history-item ${item.id === currentChatId ? 'active' : ''}`;
            li.textContent = item.title;
            li.onclick = () => switchChatSession(item.id);
            historyList.appendChild(li);
        });
    } catch (err) {
        console.error("Error loading history list:", err);
    }
}

// --- 4. สลับไปดูแชทเก่า ---
async function switchChatSession(chatId) {
    currentChatId = chatId;
    chatBox.innerHTML = ""; // ล้างหน้าจอแชทปัจจุบัน
    
    try {
        const res = await fetch(`/chats/${chatId}`);
        const data = await res.json();
        
        chatTitle.textContent = `MyAgent - ${data.title}`;
        
        // ยกลูปเอาข้อความเก่ามาเรนเดอร์ใหม่ทั้งหมด
        data.messages.forEach(msg => {
            renderMessage(msg.role, msg.content, msg.model, msg.total_tokens);
        });
        
        loadChatHistoryList(); // อัปเดตสถานะ Active บนแถบข้าง
    } catch (err) {
        console.error("Error loading chat context:", err);
    }
}

// --- 5. ปุ่มกดสร้างแชทใหม่ (New Chat) ---
newChatBtn.onclick = () => {
    currentChatId = null;
    chatBox.innerHTML = "";
    chatTitle.textContent = "MyAgent - New Chat";
    loadChatHistoryList();
};

// --- 6. ส่งข้อความแชท ---
async function sendMessage() {
    const text = input.value.trim();
    if (text === "") return;

    // แสดงคำถามฝั่งผู้ใช้ทันที
    renderMessage("user", text);
    input.value = "";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                message: text,
                chat_id: currentChatId // ส่ง ID ห้องปัจจุบันไปด้วย (ถ้ามี)
            })
        });

        const data = await response.json();
        
        // อัปเดต ID เซสชันปัจจุบันที่เซิร์ฟเวอร์ผูกคืนกลับมาให้
        currentChatId = data.chat_id;
        chatTitle.textContent = `MyAgent - ${data.title}`;

        // แสดงคำตอบบอทพร้อมโทเคน
        renderMessage("ai", data.reply, data.model, data.total_tokens);
        
        // รีโหลดแถบข้างเพื่อให้อัปเดตชื่อหัวข้อแชทใหม่
        loadChatHistoryList();
    } catch (error) {
        renderMessage("ai", "⚠️ Could not sync transaction data upstream with the network server.");
    }
}

// --- 7. ผูกปุ่มกดส่งงานตามปกติ ---
button.onclick = sendMessage;
input.onkeydown = function (e) {
    if (e.key === "Enter") {
        sendMessage();
    }
};

// รันครั้งแรกตอนโหลดหน้าเว็บเพื่อดึงรายการประวัติ
loadChatHistoryList();
