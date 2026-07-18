const input = document.getElementById("message-input");
const button = document.getElementById("send-button");
const chatBox = document.getElementById("chat-box");
const historyList = document.getElementById("history-list");
const newChatBtn = document.getElementById("new-chat-btn");
const toggleSidebarBtn = document.getElementById("toggle-sidebar-btn");
const openSidebarBtn = document.getElementById("open-sidebar-btn");
const sidebar = document.getElementById("sidebar");
const chatTitle = document.getElementById("chat-title");

const toggleMemoryBtn = document.getElementById("toggle-memory-btn");
const closeMemoryBtn = document.getElementById("close-memory-btn");
const memoryDrawer = document.getElementById("memory-drawer");
const memoryList = document.getElementById("memory-list");
const typingIndicator = document.getElementById("typing-indicator");

let currentChatId = null;
let isTypingActive = false;

// จัดการการเปิด-ปิดแถบเมนูข้างซ้ายแบบ ChatGPT
toggleSidebarBtn.onclick = () => {
    sidebar.classList.add("closed");
    openSidebarBtn.classList.remove("hidden");
};

openSidebarBtn.onclick = () => {
    sidebar.classList.remove("closed");
    openSidebarBtn.classList.add("hidden");
};

toggleMemoryBtn.onclick = () => {
    memoryDrawer.classList.toggle("closed");
    if (!memoryDrawer.classList.contains("closed")) {
        loadMemoriesList();
    }
};

closeMemoryBtn.onclick = () => {
    memoryDrawer.classList.add("closed");
};

// เร่งความเร็วพิมพ์ดีด 300% (ดีเลย์ 5ms)
function runTypewriterEffect(element, fullContent, speed = 5) {
    return new Promise((resolve) => {
        let currentText = "";
        let index = 0;
        
        function type() {
            if (index < fullContent.length) {
                currentText += fullContent.charAt(index);
                element.innerHTML = marked.parse(currentText);
                index++;
                chatBox.scrollTop = chatBox.scrollHeight;
                setTimeout(type, speed);
            } else {
                element.innerHTML = marked.parse(fullContent);
                resolve();
            }
        }
        type();
    });
}

function toggleTyping(show) {
    if (show) {
        typingIndicator.classList.remove("hidden");
    } else {
        typingIndicator.classList.add("hidden");
    }
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function renderMessage(role, content, model = null, tokens = 0, useTypewriter = false) {
    const rowDiv = document.createElement("div");
    rowDiv.className = `message-row ${role === "user" ? "user-row" : "ai-row"}`;
    
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    
    const avatarDiv = document.createElement("div");
    avatarDiv.className = "avatar";
    avatarDiv.textContent = role === "user" ? "U" : "A";
    
    const textBody = document.createElement("div");
    textBody.className = role === "user" ? "text-body" : "text-body markdown-body";
    
    contentDiv.appendChild(avatarDiv);
    contentDiv.appendChild(textBody);
    rowDiv.appendChild(contentDiv);
    chatBox.appendChild(rowDiv);
    
    if (role === "user") {
        textBody.textContent = content;
        chatBox.scrollTop = chatBox.scrollHeight;
    } else {
        if (useTypewriter) {
            isTypingActive = true;
            await runTypewriterEffect(textBody, content, 5);
            isTypingActive = false;
        } else {
            textBody.innerHTML = marked.parse(content);
        }
        
        if (model) {
            const badge = document.createElement("span");
            badge.className = "info-badge";
            badge.textContent = `Model: ${model} | Tokens: ${tokens}`;
            textBody.appendChild(badge);
        }

        // โค้ดปุ่มคัดลอก (Copy Button Logic)
        textBody.querySelectorAll("pre").forEach((preBlock) => {
            const codeBlock = preBlock.querySelector("code");
            if (!codeBlock) return;

            const copyBtn = document.createElement("button");
            copyBtn.className = "copy-code-btn pop-btn";
            copyBtn.textContent = "📋 Copy";

            copyBtn.onclick = async () => {
                const textToCopy = codeBlock.innerText;
                try {
                    await navigator.clipboard.writeText(textToCopy);
                    copyBtn.textContent = "✅ Copied!";
                    setTimeout(() => copyBtn.textContent = "📋 Copy", 2000);
                } catch (err) {
                    copyBtn.textContent = "❌ Error";
                }
            };
            preBlock.appendChild(copyBtn);
        });

        textBody.querySelectorAll("pre code").forEach((block) => {
            hljs.highlightElement(block);
        });
        
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

// 📌 ฟังก์ชันจัดการฝั่งเซสชันห้องแชท (แก้ไขจุดที่หายไป)
async function switchChatSession(chatId) {
    currentChatId = chatId;
    chatBox.innerHTML = "";
    
    try {
        const res = await fetch(`/chats/${chatId}`);
        const data = await res.json();
        chatTitle.textContent = data.title;
        
        data.messages.forEach(msg => {
            renderMessage(msg.role, msg.content, msg.model, msg.total_tokens, false);
        });
        
        loadChatHistoryList();
    } catch (err) {
        console.error("Error shifting chat context:", err);
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
                chatTitle.textContent = newTitle;
            }
            loadChatHistoryList();
        }
    } catch (err) {
        console.error("Error renaming session:", err);
    }
}

async function deleteChatSession(chatId) {
    try {
        const res = await fetch(`/chats/${chatId}`, { method: "DELETE" });
        if (res.ok) {
            if (currentChatId === chatId) {
                currentChatId = null;
                chatBox.innerHTML = "";
                chatTitle.textContent = "ChatGPT 4o";
            }
            loadChatHistoryList();
        }
    } catch (err) {
        console.error("Error destroying session:", err);
    }
}

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
                if (isTypingActive) return;
                switchChatSession(item.id);
            };
            
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "chat-actions";
            
            // ใส่คลาส pop-btn ให้ปุ่มบนไอเท็มแชทเด้งดึ๋งได้เวลาคลิก
            actionsDiv.innerHTML = `
                <button class="action-chat-btn rename-btn pop-btn" title="Rename">✏️</button>
                <button class="action-chat-btn delete-btn pop-btn" title="Delete">🗑️</button>
            `;
            
            actionsDiv.querySelector(".rename-btn").onclick = (e) => {
                e.stopPropagation();
                const newTitle = prompt("ชื่อแชทใหม่:", item.title);
                if (newTitle && newTitle.trim() !== "") renameChatSession(item.id, newTitle.trim());
            };
            
            actionsDiv.querySelector(".delete-btn").onclick = (e) => {
                e.stopPropagation();
                if (confirm(`คุณต้องการลบแชทนี้ใช่หรือไม่?`)) deleteChatSession(item.id);
            };
            
            li.appendChild(textSpan);
            li.appendChild(actionsDiv);
            historyList.appendChild(li);
        });
    } catch (err) {
        console.error(err);
    }
}

async function sendMessage() {
    if (isTypingActive) return;
    
    const text = input.value.trim();
    if (text === "") return;

    renderMessage("user", text);
    input.value = "";
    toggleTyping(true);

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text, chat_id: currentChatId })
        });

        const data = await response.json();
        currentChatId = data.chat_id;
        chatTitle.textContent = data.title;

        toggleTyping(false);
        await renderMessage("ai", data.reply, data.model, data.total_tokens, true);
        loadChatHistoryList();
    } catch (error) {
        toggleTyping(false);
        renderMessage("ai", "⚠️ Connection error occurred.");
    }
}

newChatBtn.onclick = () => {
    if (isTypingActive) return;
    currentChatId = null;
    chatBox.innerHTML = "";
    chatTitle.textContent = "ChatGPT 4o";
    loadChatHistoryList();
};

// ฟังก์ชันดึงข้อมูล Long-term Memory
async function loadMemoriesList() {
    const res = await fetch("/memory");
    const data = await res.json();
    memoryList.innerHTML = data.memories.length === 0 ? `<li style="text-align:center;color:var(--text-muted);font-size:13px;padding-top:20px;">No context stored yet.</li>` : "";
    data.memories.forEach((fact, index) => {
        const li = document.createElement("li");
        li.className = "memory-item";
        li.innerHTML = `<span>${fact}</span><button class="memory-delete-btn pop-btn" onclick="deleteMemoryFact(${index})">🗑️</button>`;
        memoryList.appendChild(li);
    });
}

async function deleteMemoryFact(index) {
    await fetch(`/memory/${index}`, { method: "DELETE" });
    loadMemoriesList();
}

button.onclick = sendMessage;
input.onkeydown = (e) => { if (e.key === "Enter") sendMessage(); };
loadChatHistoryList();