// Register GDScript language for highlight.js to enable Godot script syntax highlighting
if (typeof hljs !== 'undefined') {
    hljs.registerLanguage("gdscript", function() {
        "use strict";
        return {
            aliases: ["godot", "gdscript"],
            keywords: {
                keyword: "and in not or self void as assert breakpoint class class_name extends is func setget signal tool yield const enum export onready static var remote sync master puppet remotesync mastersync puppetsync Color8 ColorN abs asin assert atan atan2 bytes2var cartesian2polar ceil char clamp convert cos cosh db2linear decimals dectime deg2rad dict2inst ease exp floor fmod fposmod funcref get_stack hash inst2dict instance_from_id inverse_lerp is_equal_approx is_inf is_instance_valid is_nan is_zero_approx len lerp lerp_angle linear2db load log max min move_toward nearest_po2 ord parse_json polar2cartesian posmod pow preload print print_debug print_stack printerr printraw prints printt push_error push_warning rad2deg rand_range rand_seed randf randi randomize range range_lerp round seed sign sin sinh smoothstep sqrt step_decimals stepify str str2var tan tanh to_json type_exists typeof validate_json var2bytes var2str weakref wrapf wrapi yield PI TAU INF NAN int float true false null",
                control_flow_keyword: "if elif else for match break continue while pass return",
                base_type: "String Array Dictionary Vector2 Vector3 Rect2 PoolByteArray PoolColorArray PoolIntArray PoolRealArray PoolStringArray PoolVector2Array PoolVector3Array"
            },
            contains: [
                { className: "number", begin: hljs.C_NUMBER_RE },
                hljs.HASH_COMMENT_MODE,
                { className: "comment", begin: /"""/, end: /"""/ },
                hljs.QUOTE_STRING_MODE,
                {
                    variants: [
                        { className: "function", beginKeywords: "func" },
                        { className: "class", beginKeywords: "class" }
                    ],
                    end: /\w*(?=[?()]{2,})/,
                    contains: [hljs.UNDERSCORE_TITLE_MODE]
                }
            ]
        };
    });
}

// Determine backend API URL (useful for cross-origin hosting e.g. Vercel client calling Railway backend)
const API_BASE = (() => {
    let url = window.BACKEND_API_URL || "";
    if (url) {
        if (!url.startsWith("http://") && !url.startsWith("https://")) {
            url = "https://" + url;
        }
        if (url.endsWith("/")) {
            url = url.slice(0, -1);
        }
    }
    return url;
})();

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

// Elements for File Upload & Attachment Dropdown Menu
const attachmentBtn = document.getElementById("attachment-btn");
const fileInput = document.getElementById("file-input");
const filePreviewBar = document.getElementById("file-preview-bar");

const attachmentMenu = document.getElementById("attachment-menu");
const menuUploadFileBtn = document.getElementById("menu-upload-file-btn");
const menuGithubImportBtn = document.getElementById("menu-github-import-btn");
const ideFileUploadInput = document.getElementById("ide-file-upload-input");

// Elements for GitHub Import Modal
const githubModal = document.getElementById("github-modal");
const githubCloseBtn = document.getElementById("github-close-btn");
const githubTokenInput = document.getElementById("github-token-input");
const githubConnectBtn = document.getElementById("github-connect-btn");
const githubReposSection = document.getElementById("github-repos-section");
const githubRepoSelect = document.getElementById("github-repo-select");
const githubImportSubmitBtn = document.getElementById("github-import-submit-btn");

let currentChatId = null;
let isTypingActive = false;
let isWebSearchEnabled = false;
let selectedFiles = [];
let currentChatMessages = [];

// Save active session state to localStorage
function saveChatToLocalStorage() {
    localStorage.setItem("myagent_chat_history", JSON.stringify(currentChatMessages));
    localStorage.setItem("myagent_chat_id", currentChatId || "");
    localStorage.setItem("myagent_chat_title", chatTitle.textContent || "ChatGPT 4o");
}

// Load active session state from localStorage on page refresh
function loadChatFromLocalStorage() {
    try {
        const savedHistory = localStorage.getItem("myagent_chat_history");
        const savedId = localStorage.getItem("myagent_chat_id");
        const savedTitle = localStorage.getItem("myagent_chat_title");

        if (savedHistory) {
            currentChatMessages = JSON.parse(savedHistory);
            currentChatId = savedId || null;
            chatTitle.textContent = savedTitle || "ChatGPT 4o";

            chatBox.innerHTML = "";
            currentChatMessages.forEach(m => {
                renderStaticMessage(m.role, m.content, m.model, m.total_tokens);
            });
            console.log("Restored chat history from localStorage");
        }
    } catch (e) {
        console.error("Failed to load chat history from localStorage", e);
    }
}

// Toggle attachment dropdown menu
if (attachmentBtn && attachmentMenu) {
    attachmentBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        attachmentMenu.classList.toggle("hidden");
    };

    // Close dropdown menu when clicking anywhere else
    document.addEventListener("click", () => {
        attachmentMenu.classList.add("hidden");
    });
}

// Upload file list click (for chat attachments)
if (menuUploadFileBtn && fileInput) {
    menuUploadFileBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        attachmentMenu.classList.add("hidden");
        fileInput.click();
    };
}

// direct direct Upload file to backend workspace
if (ideFileUploadInput) {
    ideFileUploadInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        ideFileUploadInput.value = ""; // reset

        const formData = new FormData();
        formData.append("file", file);

        try {
            const resp = await fetch(`${API_BASE}/api/upload-file`, {
                method: "POST",
                body: formData
            });
            const data = await resp.json();
            if (resp.status === 200 || data.status === "success") {
                showCustomModal({
                    title: "Upload Successful",
                    message: `ไฟล์ ${file.name} ได้รับการอัปโหลดเซฟลงใน Workspace เรียบร้อยแล้ว!`
                });
            } else {
                showCustomModal({
                    title: "Upload Failed",
                    message: `ไม่สามารถอัปโหลดไฟล์ได้: ${data.detail || "Unknown error"}`
                });
            }
        } catch (err) {
            console.error(err);
            showCustomModal({
                title: "Upload Error",
                message: "เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์หลังบ้าน"
            });
        }
    };
}

// GitHub Modal display trigger
if (menuGithubImportBtn && githubModal) {
    menuGithubImportBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        attachmentMenu.classList.add("hidden");
        githubModal.classList.remove("hidden");

        // Load saved GitHub PAT
        const savedToken = localStorage.getItem("github_pat");
        if (savedToken) {
            githubTokenInput.value = savedToken;
        }
    };
}

if (githubCloseBtn && githubModal) {
    githubCloseBtn.onclick = () => {
        githubModal.classList.add("hidden");
    };
}

// Connect GitHub Account & fetch Repositories
if (githubConnectBtn) {
    githubConnectBtn.onclick = async () => {
        const token = githubTokenInput.value.trim();
        if (!token) {
            showCustomModal({
                title: "Authentication Error",
                message: "กรุณากรอก GitHub Personal Access Token"
            });
            return;
        }

        githubConnectBtn.textContent = "Connecting...";
        githubConnectBtn.disabled = true;

        try {
            const resp = await fetch(`${API_BASE}/api/github/repos`, {
                method: "GET",
                headers: {
                    "X-GitHub-Token": token
                }
            });
            const data = await resp.json();

            githubConnectBtn.textContent = "Connect GitHub Account";
            githubConnectBtn.disabled = false;

            if (data.status === "success" && data.repos) {
                // Save PAT
                localStorage.setItem("github_pat", token);

                // Clear and populate repositories select dropdown
                githubRepoSelect.innerHTML = "";
                data.repos.forEach(repo => {
                    const opt = document.createElement("option");
                    opt.value = repo.clone_url;
                    opt.textContent = `${repo.full_name} (${repo.private ? "Private" : "Public"})`;
                    githubRepoSelect.appendChild(opt);
                });

                githubReposSection.classList.remove("hidden");
            } else {
                showCustomModal({
                    title: "Connection Failed",
                    message: data.message || "ไม่สามารถเชื่อมต่อ GitHub ได้ ตรวจสอบ Token ของคุณอีกครั้ง"
                });
            }
        } catch (err) {
            console.error(err);
            githubConnectBtn.textContent = "Connect GitHub Account";
            githubConnectBtn.disabled = false;
            showCustomModal({
                title: "Network Error",
                message: "เชื่อมต่อหลังบ้านล้มเหลว กรุณาลองใหม่อีกครั้ง"
            });
        }
    };
}

// Clone GitHub Repository into Workspace
if (githubImportSubmitBtn) {
    githubImportSubmitBtn.onclick = async () => {
        const selectedCloneUrl = githubRepoSelect.value;
        const token = githubTokenInput.value.trim();
        if (!selectedCloneUrl) return;

        githubImportSubmitBtn.textContent = "Cloning repository...";
        githubImportSubmitBtn.disabled = true;

        try {
            const resp = await fetch(`${API_BASE}/api/github/clone`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    repo_url: selectedCloneUrl,
                    token: token
                })
            });
            const data = await resp.json();

            githubImportSubmitBtn.textContent = "Clone Repo into Workspace";
            githubImportSubmitBtn.disabled = false;
            githubModal.classList.add("hidden");

            if (data.status === "success") {
                const repoName = selectedCloneUrl.split('/').pop().replace('.git', '');
                showCustomModal({
                    title: "Import Successful",
                    message: `โคลน Repository "${repoName}" ลงใน Workspace สำเร็จแล้ว! กำลังส่งสัญญาณแจ้งเตือนระบบ...`
                });

                // Automatically notify the AI agent with a system hidden message to update context
                setTimeout(() => {
                    input.value = `[SYSTEM]: Repository ${repoName} has been imported to workspace directory successfully.`;
                    sendMessage();
                }, 800);
            } else {
                showCustomModal({
                    title: "Import Failed",
                    message: data.message || "โคลนล้มเหลว ตรวจสอบความถูกต้องของ Repo"
                });
            }
        } catch (err) {
            console.error(err);
            githubImportSubmitBtn.textContent = "Clone Repo into Workspace";
            githubImportSubmitBtn.disabled = false;
            showCustomModal({
                title: "Network Error",
                message: "เกิดข้อผิดพลาดในการโคลนเชื่อมต่อกับหลังบ้าน"
            });
        }
    };
}

// Handle selected files for attachments (e.g. text/image)
if (fileInput) {
    fileInput.onchange = (e) => {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
                selectedFiles.push(file);
            }
        });
        fileInput.value = "";
        renderFilePreviews();
    };
}

// Function to render preview of attached files
function renderFilePreviews() {
    if (!filePreviewBar) return;
    filePreviewBar.innerHTML = "";

    if (selectedFiles.length === 0) {
        filePreviewBar.classList.add("hidden");
        return;
    }

    filePreviewBar.classList.remove("hidden");

    selectedFiles.forEach((file, index) => {
        const previewItem = document.createElement("div");
        previewItem.className = "preview-item";

        // Remove button (X)
        const removeBtn = document.createElement("button");
        removeBtn.className = "preview-item-remove";
        removeBtn.innerHTML = "✕";
        removeBtn.type = "button";
        removeBtn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            selectedFiles.splice(index, 1);
            renderFilePreviews();
        };

        // File thumbnail / icon depending on file type
        if (file.type.startsWith("image/")) {
            const img = document.createElement("img");
            img.alt = file.name;
            const reader = new FileReader();
            reader.onload = (event) => {
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
            previewItem.appendChild(img);
        } else {
            // Document preview (txt or pdf)
            const docDiv = document.createElement("div");
            docDiv.className = "preview-item-doc";
            
            const ext = file.name.split('.').pop().toUpperCase();
            
            docDiv.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                </svg>
                <span>${ext}</span>
            `;
            previewItem.appendChild(docDiv);
        }

        previewItem.appendChild(removeBtn);
        filePreviewBar.appendChild(previewItem);
    });
}

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

// 🛠️ Helper to render Real-time Workflow / Status progression display inside the current AI message block
function updateWorkflowStatus(aiTextBody, text) {
    let statusContainer = aiTextBody.querySelector(".status-badge-container");
    if (!statusContainer) {
        statusContainer = document.createElement("div");
        statusContainer.className = "status-badge-container";
        statusContainer.innerHTML = `
            <span class="status-badge-spinner">⚙️</span>
            <span class="status-badge-text"></span>
        `;
        aiTextBody.appendChild(statusContainer);
    }
    statusContainer.querySelector(".status-badge-text").textContent = text;
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
    if (isTypingActive) return;
    const text = input.value.trim();
    if (text === "" && selectedFiles.length === 0) return;

    let userDisplayMessage = text;
    if (selectedFiles.length > 0) {
        const fileNames = selectedFiles.map(f => `📎 ${f.name}`).join(", ");
        if (userDisplayMessage !== "") {
            userDisplayMessage += `\n\n(${fileNames})`;
        } else {
            userDisplayMessage = fileNames;
        }
    }

    renderStaticMessage("user", userDisplayMessage);
    currentChatMessages.push({ role: "user", content: userDisplayMessage });
    saveChatToLocalStorage();
    
    const formData = new FormData();
    formData.append("message", text);
    if (currentChatId) {
        formData.append("chat_id", currentChatId);
    }
    formData.append("search_web", isWebSearchEnabled ? "true" : "false");
    
    selectedFiles.forEach(file => {
        formData.append("files", file);
    });

    input.value = "";
    const filesSent = [...selectedFiles];
    selectedFiles = [];
    renderFilePreviews();

    toggleTyping(true);

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: {
                "Accept": "text/event-stream"
            },
            body: formData
        });

        toggleTyping(false);

        const aiTextBody = createMessageLayout("ai");
        updateWorkflowStatus(aiTextBody, "Thinking / Processing...");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let finalReplyText = "";
        let finalModel = null;
        let finalTokens = 0;

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep partial line in buffer

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith("data: ")) {
                    const jsonStr = trimmed.slice(6);
                    try {
                        const data = JSON.parse(jsonStr);
                        if (data.type === "status") {
                            updateWorkflowStatus(aiTextBody, data.message);
                        } else if (data.type === "final") {
                            // Remove progress indicator once final answer starts typing
                            const statusContainer = aiTextBody.querySelector(".status-badge-container");
                            if (statusContainer) statusContainer.remove();

                            if (data.chat_id) currentChatId = data.chat_id;
                            if (data.title) chatTitle.textContent = data.title;

                            finalReplyText = data.reply;
                            finalModel = data.model;
                            finalTokens = data.total_tokens;
                        } else if (data.type === "error") {
                            const statusContainer = aiTextBody.querySelector(".status-badge-container");
                            if (statusContainer) statusContainer.remove();
                            aiTextBody.textContent = `⚠️ Error: ${data.message}`;
                        }
                    } catch (e) {
                        console.error("Failed to parse SSE line JSON", e);
                    }
                }
            }
        }

        if (finalReplyText) {
            currentChatMessages.push({
                role: "ai",
                content: finalReplyText,
                model: finalModel,
                total_tokens: finalTokens
            });
            saveChatToLocalStorage();
            await simulateStreamingMessage(aiTextBody, finalReplyText, finalModel, finalTokens);
        }
        
        loadChatHistoryList();
    } catch (error) {
        console.error(error);
        toggleTyping(false);
        renderStaticMessage("ai", "⚠️ Connection stream broke off or network timed out.");
        if (filesSent.length > 0 && selectedFiles.length === 0) {
            selectedFiles = filesSent;
            renderFilePreviews();
        }
    }
}

// Custom Modal Overlay system
function showCustomModal({ title, message, showInput = false, defaultValue = "", okText = "OK", cancelText = "Cancel" }) {
    return new Promise((resolve) => {
        const modal = document.getElementById("custom-modal");
        const modalTitle = document.getElementById("modal-title");
        const modalMessage = document.getElementById("modal-message");
        const modalInput = document.getElementById("modal-input");
        const okBtn = document.getElementById("modal-ok-btn");
        const cancelBtn = document.getElementById("modal-cancel-btn");
        const closeBtn = document.getElementById("modal-close-btn");

        modalTitle.textContent = title || "MyAgent AI";
        modalMessage.textContent = message || "";
        
        if (showInput) {
            modalInput.classList.remove("hidden");
            modalInput.value = defaultValue;
            setTimeout(() => modalInput.focus(), 50);
        } else {
            modalInput.classList.add("hidden");
            modalInput.value = "";
        }

        okBtn.textContent = okText;
        cancelBtn.textContent = cancelText;

        modal.classList.remove("hidden");

        const cleanupAndResolve = (value) => {
            modal.classList.add("hidden");
            okBtn.onclick = null;
            cancelBtn.onclick = null;
            closeBtn.onclick = null;
            modalInput.onkeydown = null;
            resolve(value);
        };

        okBtn.onclick = () => {
            if (showInput) {
                cleanupAndResolve(modalInput.value.trim());
            } else {
                cleanupAndResolve(true);
            }
        };

        cancelBtn.onclick = () => cleanupAndResolve(showInput ? null : false);
        closeBtn.onclick = () => cleanupAndResolve(showInput ? null : false);

        modalInput.onkeydown = (e) => {
            if (e.key === "Enter") {
                okBtn.click();
            } else if (e.key === "Escape") {
                cancelBtn.click();
            }
        };
    });
}

async function loadChatHistoryList() {
    try {
        const res = await fetch(`${API_BASE}/chats`);
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
                const t = await showCustomModal({
                    title: "แก้ไขชื่อห้องแชท",
                    message: "กรุณาระบุชื่อแชทใหม่:",
                    showInput: true,
                    defaultValue: item.title,
                    okText: "บันทึก",
                    cancelText: "ยกเลิก"
                });
                if (t && t.trim() !== "") renameChatSession(item.id, t.trim()); 
            };

            const handleDelete = async (e) => {
                e.preventDefault();
                e.stopPropagation(); 
                const confirmDelete = await showCustomModal({
                    title: "ลบห้องแชท",
                    message: `คุณต้องการลบห้องแชท "${item.title}" นี้ใช่หรือไม่?`,
                    okText: "ลบ",
                    cancelText: "ยกเลิก"
                });
                if (confirmDelete) deleteChatSession(item.id); 
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

async function switchChatSession(cId) {
    currentChatId = cId;
    chatBox.innerHTML = "";
    const res = await fetch(`${API_BASE}/chats/${cId}`);
    const d = await res.json();
    chatTitle.textContent = d.title;
    currentChatMessages = d.messages || [];
    currentChatMessages.forEach(m => renderStaticMessage(m.role, m.content, m.model, m.total_tokens));
    saveChatToLocalStorage();
    loadChatHistoryList();
}

async function renameChatSession(cId, title) {
    await fetch(`${API_BASE}/chats/${cId}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }) });
    if (currentChatId === cId) {
        chatTitle.textContent = title;
        localStorage.setItem("myagent_chat_title", title);
    }
    loadChatHistoryList();
}

async function deleteChatSession(cId) {
    await fetch(`${API_BASE}/chats/${cId}`, { method: "DELETE" });
    if (currentChatId === cId) {
        currentChatId = null;
        chatBox.innerHTML = "";
        chatTitle.textContent = "ChatGPT 4o";
        currentChatMessages = [];
        localStorage.removeItem("myagent_chat_history");
        localStorage.removeItem("myagent_chat_id");
        localStorage.removeItem("myagent_chat_title");
    }
    loadChatHistoryList();
}

async function loadMemoriesList() { const res = await fetch(`${API_BASE}/memory`); const d = await res.json(); memoryList.innerHTML = d.memories.length === 0 ? "<li>No memory</li>" : ""; d.memories.forEach((f, i) => { const li = document.createElement("li"); li.className = "memory-item"; li.innerHTML = `<span>${f}</span><button class="memory-delete-btn pop-btn" onclick="deleteMemoryFact(${i})">🗑️</button>`; memoryList.appendChild(li); }); }
async function deleteMemoryFact(i) { await fetch(`${API_BASE}/memory/${i}`, { method: "DELETE" }); loadMemoriesList(); }

newChatBtn.onclick = () => {
    if (!isTypingActive) {
        currentChatId = null;
        chatBox.innerHTML = "";
        chatTitle.textContent = "ChatGPT 4o";
        currentChatMessages = [];
        localStorage.removeItem("myagent_chat_history");
        localStorage.removeItem("myagent_chat_id");
        localStorage.removeItem("myagent_chat_title");
        loadChatHistoryList();
    }
};

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

if (window.innerWidth <= 768) {
    sidebar.classList.add("closed");
    openSidebarBtn.classList.remove("hidden");
}

loadChatHistoryList();
loadChatFromLocalStorage();
