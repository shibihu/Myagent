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
const searchWebToggle = document.getElementById("search-web-toggle");

let currentChatId = null;
let isTypingActive = false;
let isWebSearchEnabled = false; // สถานะเก็บว่าสั่งให้บอทค้นหาเว็บสดๆ ไหม

// เปิด-ปิดระบบทริกเกอร์ค้นหาเว็บสดๆ แบบ ChatGPT สลับสีกระพริบ
searchWebToggle.onclick = () => {
    isWebSearchEnabled = !isWebSearchEnabled;
    searchWebToggle.classList.toggle("active", isWebSearchEnabled);
};

toggleSidebarBtn.onclick = () => { sidebar.classList.add("closed"); openSidebarBtn.classList.remove("hidden"); };
openSidebarBtn.onclick = () => { sidebar.classList.remove("closed"); openSidebarBtn.classList.add("hidden"); };
toggleMemoryBtn.onclick = () => { memoryDrawer.classList.toggle("closed"); if (!memoryDrawer.classList.contains("closed")) loadMemoriesList(); };
closeMemoryBtn.onclick = () => { memoryDrawer.classList.add("closed"); };

function toggleTyping(show) {
    if (show) typingIndicator.classList.remove("hidden");
    else typingIndicator.classList.add("hidden");
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ฟังก์ชันสร้างกลุ่มข้อความและประมวลผลข้อความไหลพรั่งพรูผ่าน Fetch Text Stream Decoder
async function renderStreamingMessage(textBodyElement, streamResponse) {
    const reader = streamResponse.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let accumulatedText = "";

    isTypingActive = true;
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        // ถอดรหัสชิ้นส่วนคำที่ส่งตรงมาจาก Server หลังบ้านแบบเสี้ยววินาที
        const chunk = decoder.decode(value, { stream: true });
        accumulatedText += chunk;
        
        // อัปเดตข้อความบนหน้าจอทันทีแบบพรั่งพรูไร้รอยต่อ
        textBodyElement.innerHTML = marked.parse(accumulatedText);
        chatBox.scrollTop = chatBox.scrollHeight;
    }
    isTypingActive = false;
    
    // หลังสตรีมจบ ค่อยทำการเรนเดอร์ปุ่ม Copy โค้ดและทำสัญลักษณ์ Highlight 
    setupMessageUtilities(textBodyElement);
}

function createMessageLayout(role) {
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
    return textBody;
}

function setupMessageUtilities(textBody) {
    textBody.querySelectorAll("pre").forEach((preBlock) => {
        const codeBlock = preBlock.querySelector("code");
        if (!codeBlock) return;
        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-code-btn pop-btn";
        copyBtn.textContent = "📋 Copy";
        copyBtn.onclick = async () => {
            try {
                await navigator.clipboard.writeText(codeBlock.innerText);
                copyBtn.textContent = "✅ Copied!";
                setTimeout(() => copyBtn.textContent = "📋 Copy", 2000);
            } catch (err) { copyBtn.textContent = "❌ Error"; }
        };
        preBlock.appendChild(copyBtn);
    });
    textBody.querySelectorAll("pre code").forEach((block) => { hljs.highlightElement(block); });
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function renderStaticMessage(role, content, model = null, tokens = 0) {
    const textBody = createMessageLayout(role);
    if (role === "user") {
        textBody.textContent = content;
    } else {
        textBody.innerHTML = marked.parse(content);
        if (model) {
            const badge = document.createElement("span");
            badge.className = "info-badge";
            badge.textContent = `Model: ${model} | Tokens: ${tokens}`;
            textBody.appendChild(badge);
        }
        setupMessageUtilities(textBody);
    }
    chatBox.scrollTop = chatBox.scrollHeight;
}


// ฟังก์ชันส่งข้อความและเรียกใช้ตัวควบคุม Streaming + Web Search Payload
async function sendMessage() {
    if (isTypingActive) return;
    const text = input.value.trim();
    if (text === "") return;

    renderStaticMessage("user", text);
    input.value = "";
    toggleTyping(true);

    try {
        // ยิงคำขอไปที่ backend โดยส่งค่าสถานะพารามิเตอร์การค้นหาเว็บสดๆ เข้าไปด้วย
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                message: text, 
                chat_id: currentChatId,
                search_web: isWebSearchEnabled // ผูกตัวแปรส่งเข้าหลังบ้านให้ไปหาข้อมูลผ่านบ็อทเสิร์ช
            })
        });

        toggleTyping(false);
        const aiTextBody = createMessageLayout("ai");
        
        // สั่งเปิดระบบรับข้อมูลแบบสตรีมมิ่งทันทีเพื่อความเร็วระดับสูง
        await renderStreamingMessage(aiTextBody, response);
        
        // คว้าไอดีห้องแชทล่าสุดจาก Response Header หรือสร้างระบบบันทึกประวัติหลังบ้านอัตโนมัติ
        const activeChatId = response.headers.get("X-Chat-ID");
        if (activeChatId) currentChatId = activeChatId;
        
        loadChatHistoryList();
    } catch (error) {
        toggleTyping(false);
        renderStaticMessage("ai", "⚠️ Connection stream broke off or network timed out.");
    }
}

// 🛠️ ปรับเปลี่ยนหน้าตาปุ่มแก้ไข (✏️ SVG) และปุ่มลบ (🗑️ SVG) ใหม่ให้มินิมอลตามดีไซน์ ChatGPT จริง
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
            textSpan.onclick = () => { if (!isTypingActive) switchChatSession(item.id); };
            
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "chat-actions";
            
            // ไอคอนรูปดินสอและถังขยะแบบเวกเตอร์สไตล์ ChatGPT สวยงามคมชัดบนมือถือ
            actionsDiv.innerHTML = `
                <button class="action-chat-btn rename-btn pop-btn" title="Rename"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg></button>
                <button class="action-chat-btn delete-btn pop-btn" title="Delete"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></button>
            `;
            actionsDiv.querySelector(".rename-btn").onclick = (e) => { e.stopPropagation(); const t = prompt("ชื่อแชทใหม่:", item.title); if (t) renameChatSession(item.id, t.trim()); };
            actionsDiv.querySelector(".delete-btn").onclick = (e) => { e.stopPropagation(); if (confirm(`ลบแชทนี้?`)) deleteChatSession(item.id); };
            li.appendChild(textSpan); li.appendChild(actionsDiv); historyList.appendChild(li);
        });
    } catch (err) { console.error(err); }
}

async function switchChatSession(cId) { currentChatId = cId; chatBox.innerHTML = ""; const res = await fetch(`/chats/${cId}`); const d = await res.json(); chatTitle.textContent = d.title; d.messages.forEach(m => renderStaticMessage(m.role, m.content, m.model, m.total_tokens)); loadChatHistoryList(); }
async function renameChatSession(cId, title) { await fetch(`/chats/${cId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) }); loadChatHistoryList(); }
async function deleteChatSession(cId) { await fetch(`/chats/${cId}`, { method: "DELETE" }); if (currentChatId === cId) { currentChatId = null; chatBox.innerHTML = ""; chatTitle.textContent = "ChatGPT 4o"; } loadChatHistoryList(); }
async function loadMemoriesList() { const res = await fetch("/memory"); const d = await res.json(); memoryList.innerHTML = d.memories.length === 0 ? "<li>No memory</li>" : ""; d.memories.forEach((f, i) => { const li = document.createElement("li"); li.className = "memory-item"; li.innerHTML = `<span>${f}</span><button class="memory-delete-btn pop-btn" onclick="deleteMemoryFact(${i})">🗑️</button>`; memoryList.appendChild(li); }); }
async function deleteMemoryFact(i) { await fetch(`/memory/${i}`, { method: "DELETE" }); loadMemoriesList(); }

newChatBtn.onclick = () => { if (!isTypingActive) { currentChatId = null; chatBox.innerHTML = ""; chatTitle.textContent = "ChatGPT 4o"; loadChatHistoryList(); } };
button.onclick = sendMessage;
input.onkeydown = (e) => { if (e.key === "Enter") sendMessage(); };
loadChatHistoryList();

