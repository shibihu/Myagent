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

function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        return navigator.clipboard.writeText(text);
    } else {
        // Fallback using dummy element
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        textArea.style.top = "-999999px";
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        return new Promise((resolve, reject) => {
            try {
                const successful = document.execCommand('copy');
                textArea.remove();
                if (successful) {
                    resolve();
                } else {
                    reject(new Error("Fallback copy failed"));
                }
            } catch (err) {
                textArea.remove();
                reject(err);
            }
        });
    }
}

async function simulateStreamingMessage(textBodyElement, fullText, model = null, tokens = 0) {
    isTypingActive = true;
    textBodyElement.innerHTML = "";
    
    let currentText = "";
    const charsPerStep = Math.max(1, Math.floor(fullText.length / 300));
    const stepDelay = 15; // ms
    
    let index = 0;
    return new Promise((resolve) => {
        function type() {
            if (index < fullText.length) {
                currentText += fullText.slice(index, index + charsPerStep);
                index += charsPerStep;
                textBodyElement.innerHTML = marked.parse(currentText);
                chatBox.scrollTop = chatBox.scrollHeight;
                setTimeout(type, stepDelay);
            } else {
                textBodyElement.innerHTML = marked.parse(fullText);
                if (model) {
                    const badge = document.createElement("span");
                    badge.className = "info-badge";
                    badge.textContent = `Model: ${model} | Tokens: ${tokens}`;
                    textBodyElement.appendChild(badge);
                }
                setupMessageUtilities(textBodyElement);
                isTypingActive = false;
                resolve();
            }
        }
        type();
    });
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
        const oldBtn = preBlock.querySelector(".copy-code-btn");
        if (oldBtn) oldBtn.remove();

        const codeBlock = preBlock.querySelector("code");
        if (!codeBlock) return;

        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-code-btn pop-btn";
        copyBtn.setAttribute("type", "button");
        copyBtn.title = "Copy code";

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
                await copyToClipboard(codeBlock.innerText);
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
            } catch (err) {
                copyBtn.innerHTML = `<span>❌</span>`;
                setTimeout(() => {
                    copyBtn.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                    `;
                }, 2000);
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
        const data = await response.json();
        
        if (data.chat_id) {
            currentChatId = data.chat_id;
        }
        if (data.title) {
            chatTitle.textContent = data.title;
        }
        
        const aiTextBody = createMessageLayout("ai");
        await simulateStreamingMessage(aiTextBody, data.reply, data.model, data.total_tokens);
        
        loadChatHistoryList();
    } catch (error) {
        console.error(error);
        toggleTyping(false);
        renderStaticMessage("ai", "⚠️ Connection stream broke off or network timed out.");
    }
}

// Custom Popup Dialog Modals logic
const customModalOverlay = document.getElementById("custom-modal-overlay");
const modalTitle = document.getElementById("modal-title");
const modalMessage = document.getElementById("modal-message");
const modalInput = document.getElementById("modal-input");
const modalCancelBtn = document.getElementById("modal-cancel-btn");
const modalConfirmBtn = document.getElementById("modal-confirm-btn");

let activeModalResolve = null;

function showCustomPrompt(title, message, defaultValue = "") {
    return new Promise((resolve) => {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modalInput.value = defaultValue;
        modalInput.classList.remove("hidden");
        modalCancelBtn.classList.remove("hidden");
        customModalOverlay.classList.remove("hidden");
        modalInput.focus();
        
        activeModalResolve = (val) => {
            customModalOverlay.classList.add("hidden");
            resolve(val);
        };
    });
}

function showCustomConfirm(title, message) {
    return new Promise((resolve) => {
        modalTitle.textContent = title;
        modalMessage.textContent = message;
        modalInput.classList.add("hidden");
        modalCancelBtn.classList.remove("hidden");
        customModalOverlay.classList.remove("hidden");
        
        activeModalResolve = (val) => {
            customModalOverlay.classList.add("hidden");
            resolve(val);
        };
    });
}

modalConfirmBtn.onclick = () => {
    if (activeModalResolve) {
        if (!modalInput.classList.contains("hidden")) {
            activeModalResolve(modalInput.value);
        } else {
            activeModalResolve(true);
        }
    }
};

modalCancelBtn.onclick = () => {
    if (activeModalResolve) {
        activeModalResolve(null);
    }
};

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
                <button class="action-chat-btn delete-btn pop-btn" title="Delete" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></button>
            `;
            
            const renameBtn = actionsDiv.querySelector(".rename-btn");
            const deleteBtn = actionsDiv.querySelector(".delete-btn");

            const handleRename = async (e) => {
                e.preventDefault();
                e.stopPropagation(); 
                const t = await showCustomPrompt("ชื่อแชทใหม่:", "เปลี่ยนชื่อห้องแชทของคุณ:", item.title); 
                if (t && t.trim() !== "") renameChatSession(item.id, t.trim()); 
            };

            const handleDelete = async (e) => {
                e.preventDefault();
                e.stopPropagation(); 
                const isConfirmed = await showCustomConfirm("ลบแชท", `คุณต้องการลบห้องแชท "${item.title}" ใช่หรือไม่?`);
                if (isConfirmed) deleteChatSession(item.id); 
            };

            renameBtn.onclick = handleRename;
            renameBtn.ontouchstart = (e) => e.stopPropagation();
            renameBtn.ontouchend = handleRename;

            deleteBtn.onclick = handleDelete;
            deleteBtn.ontouchstart = (e) => e.stopPropagation();
            deleteBtn.ontouchend = handleDelete;
            
            li.appendChild(textSpan); 
            li.appendChild(actionsDiv); 
            
            li.onclick = (e) => {
                if (e.target.closest('.action-chat-btn')) return;
                if (!isTypingActive) switchChatSession(item.id);
            };
            
            historyList.appendChild(li);
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

// Tap anywhere in main container to automatically close the sidebar on mobile devices
const dismissSidebarOnMobile = (e) => {
    if (window.innerWidth <= 768 && !sidebar.classList.contains("closed")) {
        if (e.target.closest("#open-sidebar-btn")) return;
        sidebar.classList.add("closed");
        openSidebarBtn.classList.remove("hidden");
    }
};
const mainContainer = document.getElementById("main-container");
if (mainContainer) {
    mainContainer.addEventListener("click", dismissSidebarOnMobile);
    mainContainer.addEventListener("touchstart", dismissSidebarOnMobile, { passive: true });
}

// On mobile, start with the sidebar closed so the main chat is visible
if (window.innerWidth <= 768) {
    sidebar.classList.add("closed");
    openSidebarBtn.classList.remove("hidden");
}

// Tab Switcher logic
const tabChat = document.getElementById("tab-chat");
const tabIde = document.getElementById("tab-ide");
const chatWorkspace = document.getElementById("chat-workspace");
const ideWorkspace = document.getElementById("ide-workspace");

if (tabChat && tabIde && chatWorkspace && ideWorkspace) {
    tabChat.onclick = () => {
        tabChat.classList.add("active");
        tabIde.classList.remove("active");
        chatWorkspace.classList.remove("hidden");
        ideWorkspace.classList.add("hidden");
    };
    tabIde.onclick = () => {
        tabIde.classList.add("active");
        tabChat.classList.remove("active");
        ideWorkspace.classList.remove("hidden");
        chatWorkspace.classList.add("hidden");
    };
}

// Cloud IDE Terminal Runner
const terminalInput = document.getElementById("terminal-input");
const terminalRunBtn = document.getElementById("terminal-run-btn");
const terminalLog = document.getElementById("terminal-log");

async function runTerminalCommand() {
    const cmd = terminalInput.value.trim();
    if (!cmd) return;
    
    terminalLog.textContent += `\n$ ${cmd}\n`;
    terminalInput.value = "";
    terminalLog.scrollTop = terminalLog.scrollHeight;
    
    try {
        const response = await fetch("/ide/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ command: cmd })
        });
        const data = await response.json();
        terminalLog.textContent += data.output || "No output returned.";
    } catch (err) {
        terminalLog.textContent += `Error executing command: ${err.message}\n`;
    }
    terminalLog.scrollTop = terminalLog.scrollHeight;
}

if (terminalRunBtn && terminalInput) {
    terminalRunBtn.onclick = runTerminalCommand;
    terminalInput.onkeydown = (e) => { if (e.key === "Enter") runTerminalCommand(); };
}

// Cloud IDE MCP Servers Connections
const mcpRenderBtn = document.getElementById("mcp-render-btn");
const mcpRobloxBtn = document.getElementById("mcp-roblox-btn");
const mcpGithubBtn = document.getElementById("mcp-github-btn");

async function toggleMCP(provider) {
    const btn = document.getElementById(`mcp-${provider}-btn`);
    const statusSpan = document.querySelector(`#mcp-${provider} .mcp-status`);
    if (!btn || !statusSpan) return;
    
    const isConnecting = btn.textContent === "Connect";
    
    try {
        const res = await fetch("/ide/mcp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider, active: isConnecting })
        });
        const data = await res.json();
        if (data.status === "success") {
            if (isConnecting) {
                btn.textContent = "Disconnect";
                btn.classList.add("connected");
                statusSpan.textContent = "Connected";
                statusSpan.className = "mcp-status connected";
            } else {
                btn.textContent = "Connect";
                btn.classList.remove("connected");
                statusSpan.textContent = "Disconnected";
                statusSpan.className = "mcp-status disconnected";
            }
        }
    } catch (err) {
        console.error(err);
    }
}

if (mcpRenderBtn) mcpRenderBtn.onclick = () => toggleMCP("render");
if (mcpRobloxBtn) mcpRobloxBtn.onclick = () => toggleMCP("roblox");
if (mcpGithubBtn) mcpGithubBtn.onclick = () => toggleMCP("github");

// Git operations
const gitCommitMsgInput = document.getElementById("git-commit-message");
const gitPushBtn = document.getElementById("git-push-btn");

if (gitPushBtn) {
    gitPushBtn.onclick = async () => {
        const msg = gitCommitMsgInput.value.trim();
        if (!msg) {
            await showCustomPrompt("🐙 Git Commit Message", "Please enter a commit message first:", "");
            return;
        }
        
        gitPushBtn.textContent = "Pushing...";
        gitPushBtn.disabled = true;
        
        try {
            const res = await fetch("/ide/git-push", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ commit_message: msg })
            });
            const data = await res.json();
            await showCustomPrompt("🐙 Git Push Complete", "GitHub status response:", data.message || "Git operations completed.");
            gitCommitMsgInput.value = "";
        } catch (err) {
            await showCustomPrompt("🐙 Git Error", "Git command failed:", err.message);
        } finally {
            gitPushBtn.textContent = "🚀 Commit & Push to GitHub";
            gitPushBtn.disabled = false;
        }
    };
}

loadChatHistoryList();
