const input = document.getElementById("message-input");
const button = document.getElementById("send-button");
const chatBox = document.getElementById("chat-box");
const historyList = document.getElementById("history-list");
const newChatBtn = document.getElementById("new-chat-btn");
const toggleSidebarBtn = document.getElementById("toggle-sidebar-btn");
const sidebar = document.getElementById("sidebar");
const chatTitle = document.getElementById("chat-title");

// Elements เพิ่มเติมสำหรับระบบความจำ
const toggleMemoryBtn = document.getElementById("toggle-memory-btn");
const closeMemoryBtn = document.getElementById("close-memory-btn");
const memoryDrawer = document.getElementById("memory-drawer");
const memoryList = document.getElementById("memory-list");

let currentChatId = null;

// สวิตช์เปิด-ปิดแถบซ้าย (ประวัติแชท)
toggleSidebarBtn.onclick = () => {
    sidebar.classList.toggle("closed");
};

// สวิตช์เปิด-ปิดแถบขวา (แผงความจำ) พร้อมสั่งดึงข้อมูลมาแสดงผลเมื่อกดเปิด
toggleMemoryBtn.onclick = () => {
    memoryDrawer.classList.toggle("closed");
    if (!memoryDrawer.classList.contains("closed")) {
        loadMemoriesList();
    }
};

closeMemoryBtn.onclick = () => {
    memoryDrawer.classList.add("closed");
};

chatBox.onclick = () => {
    if (window.innerWidth <= 768) {
        sidebar.classList.add("closed");
        memoryDrawer.classList.add("closed");
    }
};

function renderMessage(role, content, model = null, tokens = 0) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role === "user" ? "user" : "ai markdown-body"}`;
    
    if (role === "user") {
        msgDiv.textContent = content;
    } else {
        msgDiv.innerHTML = marked.parse(content);
        
        if (model) {
            const tokenBadge = document.createElement("div");
            tokenBadge.style.cssText = "font-size:11px; color:#8b949e; margin-top:10px; border-top:1px solid #30363d; padding-top:6px; display:inline-block; font-family:monospace;";
            tokenBadge.textContent = `🧠 Model: ${model} | 📊 Tokens Used: ${tokens}`;
            msgDiv.appendChild(tokenBadge);
        }

        msgDiv.querySelectorAll("pre").forEach((preBlock) => {
            const codeBlock = preBlock.querySelector("code");
            if (!codeBlock) return;

            const copyBtn = document.createElement("button");
            copyBtn.className = "copy-code-btn";
            copyBtn.textContent = "📋 Copy";

            copyBtn.onclick = async () => {
                const textToCopy = codeBlock.innerText;
                if (navigator.clipboard && window.isSecureContext) {
                    try {
                        await navigator.clipboard.writeText(textToCopy);
                        showSuccessState();
                        return;
                    } catch (err) {
                        console.error("Modern copy failed, trying fallback...", err);
                    }
                }
                try {
                    const textArea = document.createElement("textarea");
                    textArea.value = textToCopy;
                    textArea.style.position = "fixed";
                    textArea.style.left = "-999999px";
                    textArea.style.top = "-999999px";
                    document.body.appendChild(textArea);
                    textArea.focus();
                    textArea.select();
                    const successful = document.execCommand('copy');
                    document.body.removeChild(textArea);
                    if (successful) showSuccessState();
                } catch (err) {
                    copyBtn.textContent = "❌ Error";
                }
            };

            function showSuccessState() {
                copyBtn.textContent = "✅ Copied!";
                copyBtn.style.backgroundColor = "#238636";
                setTimeout(() => {
                    copyBtn.textContent = "📋 Copy";
                    copyBtn.style.backgroundColor = "#21262d";
                }, 2000);
            }

            preBlock.appendChild(copyBtn);
        });
    }

    msgDiv.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
    });

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// โหลดรายชื่อแชทบน Sidebar
async function loadChatHistoryList() {
    try {
        const res = await fetch("/chats");
        const list = await res.json();
        historyList.innerHTML = "";
        
        list.forEach(item => {
            const li = document.createElement("li");
            li.className = `history-item ${item.id === currentChatId ? 'active' : ''}`;
            
            const textSpan = document.createElement("span");
            textSpan.className = "chat-link-text";
            textSpan.textContent = item.title;
            textSpan.onclick = () => {
                switchChatSession(item.id);
                if (window.innerWidth <= 768) sidebar.classList.add("closed");
            };
            
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "chat-actions";
            
            const renameBtn = document.createElement("button");
            renameBtn.className = "action-chat-btn rename-btn";
            renameBtn.innerHTML = "✏️";
            renameBtn.title = "Rename Chat";
            renameBtn.onclick = (e) => {
                e.stopPropagation();
                const newTitle = prompt("ระบุชื่อหัวข้อแชทใหม่ของคุณ:", item.title);
                if (newTitle && newTitle.trim() !== "") {
                    renameChatSession(item.id, newTitle.trim());
                }
            };
            
            const deleteBtn = document.createElement("button");
            deleteBtn.className = "action-chat-btn delete-btn";
            deleteBtn.innerHTML = "🗑️";
            deleteBtn.title = "Delete Chat";
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                if (confirm(`คุณต้องการลบแชท "${item.title}" ใช่หรือไม่?`)) {
                    deleteChatSession(item.id);
                }
            };
            
            actionsDiv.appendChild(renameBtn);
            actionsDiv.appendChild(deleteBtn);
            
            li.appendChild(textSpan);
            li.appendChild(actionsDiv);
            historyList.appendChild(li);
        });
    } catch (err) {
        console.error("Error loading history list:", err);
    }
}

// === โหลดข้อมูลประวัติความจำ (Memory Interface Logic) ===
async function loadMemoriesList() {
    try {
        const res = await fetch("/memory");
        const data = await res.json();
        memoryList.innerHTML = "";
        
        if (data.memories.length === 0) {
            memoryList.innerHTML = `<li style="text-align:center;color:#8b949e;font-size:13px;padding-top:20px;">ยังไม่มีความจำถูกบันทึก<br>ลองแชทคุยเพื่อให้บอทเรียนรู้ดูครับ! 🤖</li>`;
            return;
        }
        
        data.memories.forEach((fact, index) => {
            const li = document.createElement("li");
            li.className = "memory-item";
            
            const span = document.createElement("span");
            span.textContent = fact;
            
            const delBtn = document.createElement("button");
            delBtn.className = "memory-delete-btn";
            delBtn.innerHTML = "🗑️";
            delBtn.title = "ลบความจำข้อนี้";
            delBtn.onclick = async () => {
                if (confirm(`ลบความจำข้อความนี้ใช่ไหม: "${fact}"`)) {
                    await deleteMemoryFact(index);
                }
            };
            
            li.appendChild(span);
            li.appendChild(delBtn);
            memoryList.appendChild(li);
        });
    } catch (err) {
        console.error("Error fetching memories:", err);
    }
}

async function deleteMemoryFact(index) {
    try {
        const res = await fetch(`/memory/${index}`, { method: "DELETE" });
        if (res.ok) {
            loadMemoriesList(); // รีเฟรชลิสต์ความจำหลังหักล้างเสร็จสิ้น
        }
    } catch (err) {
        console.error("Error deleting memory:", err);
    }
}

async function renameChatSession(chatId, newTitle) {
    try {
        const res = await fetch(`/chats/${chatId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: newTitle })
        });
        if (res.ok) {
            if (currentChatId === chatId) {
                chatTitle.textContent = `MyAgent - ${newTitle}`;
            }
            loadChatHistoryList();
        }
    } catch (err) {
        console.error("Error renaming chat:", err);
    }
}

async function deleteChatSession(chatId) {
    try {
        const res = await fetch(`/chats/${chatId}`, { method: "DELETE" });
        if (res.ok) {
            if (currentChatId === chatId) {
                currentChatId = null;
                chatBox.innerHTML = "";
                chatTitle.textContent = "MyAgent - New Chat";
            }
            loadChatHistoryList();
        }
    } catch (err) {
        console.error("Error deleting chat:", err);
    }
}

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

newChatBtn.onclick = () => {
    currentChatId = null;
    chatBox.innerHTML = "";
    chatTitle.textContent = "MyAgent - New Chat";
    loadChatHistoryList();
    if (window.innerWidth <= 768) sidebar.classList.add("closed");
};

async function sendMessage() {
    const text = input.value.trim();
    if (text === "") return;

    renderMessage("user", text);
    input.value = "";

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, chat_id: currentChatId })
        });

        if (!response.ok) {
            throw new Error(`Server returned status ${response.status}`);
        }

        const data = await response.json();
        currentChatId = data.chat_id;
        chatTitle.textContent = `MyAgent - ${data.title}`;

        renderMessage("ai", data.reply, data.model, data.total_tokens);
        loadChatHistoryList();
        
        // ถ้าหน้าต่างความจำเปิดอยู่ ให้รีเฟรชอัปเดตค่าความจำใหม่ที่อาจเกิดขึ้นหลังตอบคำถามทันที
        if (!memoryDrawer.classList.contains("closed")) {
            setTimeout(loadMemoriesList, 1000); // ดีเลย์ 1 วินาทีเพื่อให้พื้นหลังเขียนเซฟลง JSON เรียบร้อยก่อนดึงข้อมูล
        }
    } catch (error) {
        console.error(error);
        renderMessage("ai", "⚠️ Could not sync transaction data upstream with the network server.");
    }
}

button.onclick = sendMessage;
input.onkeydown = function (e) {
    if (e.key === "Enter") sendMessage();
};

loadChatHistoryList();