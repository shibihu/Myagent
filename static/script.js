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
let isWebSearchEnabled = false;

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

async function copyToClipboard(text) {
    // 1. Try standard navigator.clipboard
    if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.warn("navigator.clipboard.writeText failed, using fallback:", err);
        }
    }

    // 2. Fallback using a dummy textarea element
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";  // Prevent scrolling
    textarea.style.top = "0";
    textarea.style.left = "0";
    textarea.style.width = "2em";
    textarea.style.height = "2em";
    textarea.style.padding = "0";
    textarea.style.border = "none";
    textarea.style.outline = "none";
    textarea.style.boxShadow = "none";
    textarea.style.background = "transparent";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    
    let success = false;
    try {
        success = document.execCommand("copy");
    } catch (err) {
        console.error("Fallback document.execCommand copy failed", err);
    } finally {
        document.body.removeChild(textarea);
    }

    if (success) {
        return true;
    }

    // 3. Ultimate prompt fallback for strict sandbox environments
    const manualCopy = window.prompt("Your browser blocked direct clipboard access. Copy the code below manually:", text);
    return manualCopy !== null;
}

async function simulateStreamingMessage(textBodyElement, replyText, model = null, tokens = 0) {
    isTypingActive = true;
    textBodyElement.innerHTML = "";
    
    let currentText = "";
    const chars = Array.from(replyText); // Safe for emojis/unicode
    const step = Math.max(1, Math.floor(chars.length / 100)); // Dynamic step size so long responses don't take forever
    
    let index = 0;
    while (index < chars.length) {
        currentText += chars.slice(index, index + step).join("");
        index += step;
        textBodyElement.innerHTML = marked.parse(currentText);
        chatBox.scrollTop = chatBox.scrollHeight;
        await new Promise(resolve => setTimeout(resolve, 10));
    }
    
    // Final render to make sure it's 100% exact
    textBodyElement.innerHTML = marked.parse(replyText);
    
    if (model) {
        const badge = document.createElement("span");
        badge.className = "info-badge";
        badge.textContent = `Model: ${model} | Tokens: ${tokens}`;
        textBodyElement.appendChild(badge);
    }
    
    isTypingActive = false;
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

// 🛠️ เปลี่ยนปุ่มคัดลอกจากคำว่า "Copy" เป็นไอคอนรูปแผ่นกระดาษ/กล่องซ้อนสไตล์ Markdown จริง
function setupMessageUtilities(textBody) {
    textBody.querySelectorAll("pre").forEach((preBlock) => {
        const oldBtn = preBlock.querySelector(".copy-code-btn");
        if (oldBtn) oldBtn.remove();

        const codeBlock = preBlock.querySelector("code");
        if (!codeBlock) return;

        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-code-btn pop-btn";
        copyBtn.setAttribute("type", "button");
        copyBtn.title = "Copy code";

        // ใส่ไอคอน SVG แผ่นกระดาษซ้อนกัน (Copy Icon) ลงไปตรงๆ
        copyBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
        `;

        copyBtn.onclick = async (e) => {
            e.preventDefault();
            e.stopPropagation();
            try {
                const res = await copyToClipboard(codeBlock.innerText);
                if (res) {
                    // เมื่อก๊อปปี้สำเร็จ เปลี่ยนเป็นไอคอนติ๊กถูก (Check Icon) สั้นๆ 2 วินาที
                    copyBtn.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="#10a37f" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    `;
                    setTimeout(() => {
                        copyBtn.innerHTML = `
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                        `;
                    }, 2000);
                } else {
                    copyBtn.innerHTML = `<span>❌</span>`;
                }
            } catch (err) {
                copyBtn.innerHTML = `<span>❌</span>`;
            }
        };
        preBlock.appendChild(copyBtn);
    });

    textBody.querySelectorAll("pre code").forEach((block) => { 
        hljs.highlightElement(block); 
    });
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


async function sendMessage() {
    if (isTypingActive) return;
    const text = input.value.trim();
    if (text === "") return;

    renderStaticMessage("user", text);
    input.value = "";
    toggleTyping(true);

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                message: text, 
                chat_id: currentChatId,
                search_web: isWebSearchEnabled 
            })
        });

        toggleTyping(false);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const resData = await response.json();
        
        const aiTextBody = createMessageLayout("ai");
        
        // Update currentChatId and sidebar title
        currentChatId = resData.chat_id;
        chatTitle.textContent = resData.title;
        
        await simulateStreamingMessage(aiTextBody, resData.reply, resData.model, resData.total_tokens);
        
        loadChatHistoryList();
    } catch (error) {
        console.error(error);
        toggleTyping(false);
        renderStaticMessage("ai", "⚠️ Connection stream broke off or network timed out.");
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
            
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "chat-actions";
            
            actionsDiv.innerHTML = `
                <button class="action-chat-btn rename-btn pop-btn" title="Rename" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg></button>
                <button class="action-chat-btn delete-btn pop-btn" title="Delete" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></button>
            `;
            
            const renameBtn = actionsDiv.querySelector(".rename-btn");
            const deleteBtn = actionsDiv.querySelector(".delete-btn");

            const stopProp = (e) => {
                e.stopPropagation();
            };

            // Touch events require explicit stopPropagation to avoid triggering list selection on mobile
            renameBtn.ontouchstart = stopProp;
            renameBtn.ontouchend = stopProp;
            renameBtn.onclick = (e) => { 
                e.preventDefault();
                e.stopPropagation(); 
                const t = prompt("ชื่อแชทใหม่:", item.title); 
                if (t && t.trim() !== "") renameChatSession(item.id, t.trim()); 
            };
            
            deleteBtn.ontouchstart = stopProp;
            deleteBtn.ontouchend = stopProp;
            deleteBtn.onclick = (e) => { 
                e.preventDefault();
                e.stopPropagation(); 
                if (confirm(`คุณต้องการลบห้องแชทนี้ใช่หรือไม่?`)) deleteChatSession(item.id); 
            };
            
            li.appendChild(textSpan); 
            li.appendChild(actionsDiv); 
            
            // Set onclick on the entire li instead of just the span, making it very user-friendly
            li.onclick = (e) => {
                if (e.target.closest(".action-chat-btn") || e.target.closest(".chat-actions")) {
                    return;
                }
                if (!isTypingActive) switchChatSession(item.id);
            };
            
            historyList.appendChild(li);
        });
    } catch (err) { console.error(err); }
}

async function switchChatSession(cId) { currentChatId = cId; chatBox.innerHTML = ""; const res = await fetch(`/chats/${cId}`); const d = await res.json(); chatTitle.textContent = d.title; d.messages.forEach(m => renderStaticMessage(m.role, m.content, m.model, m.total_tokens)); loadChatHistoryList(); }
async function renameChatSession(cId, title) { await fetch(`/chats/${cId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) }); loadChatHistoryList(); }
async function deleteChatSession(cId) { await fetch(`/chats/${cId}`, { method: "DELETE" }); if (currentChatId === cId) { currentChatId = null; chatBox.innerHTML = ""; chatTitle.textContent = "ChatGPT 4o"; } loadChatHistoryList(); }

async function loadMemoriesList() { 
    const res = await fetch("/memory"); 
    const d = await res.json(); 
    memoryList.innerHTML = d.memories.length === 0 ? "<li>No memory</li>" : ""; 
    d.memories.forEach((f, i) => { 
        const li = document.createElement("li"); 
        li.className = "memory-item"; 
        li.innerHTML = `<span>${f}</span><button class="memory-delete-btn pop-btn" type="button" title="Delete memory">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 14px; height: 14px;">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
        </button>`; 
        
        const delBtn = li.querySelector(".memory-delete-btn");
        const stopProp = (e) => e.stopPropagation();
        
        delBtn.ontouchstart = stopProp;
        delBtn.ontouchend = stopProp;
        delBtn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            deleteMemoryFact(i);
        };
        
        memoryList.appendChild(li); 
    }); 
}

async function deleteMemoryFact(i) { await fetch(`/memory/${i}`, { method: "DELETE" }); loadMemoriesList(); }

newChatBtn.onclick = () => { if (!isTypingActive) { currentChatId = null; chatBox.innerHTML = ""; chatTitle.textContent = "ChatGPT 4o"; loadChatHistoryList(); } };
button.onclick = sendMessage;
input.onkeydown = (e) => { if (e.key === "Enter") sendMessage(); };
loadChatHistoryList();