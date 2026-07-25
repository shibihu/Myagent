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

// Elements for MCP Config Editor Modal
const toggleMcpBtn = document.getElementById("toggle-mcp-btn");
const mcpModal = document.getElementById("mcp-modal");
const mcpCloseBtn = document.getElementById("mcp-close-btn");
const mcpCancelBtn = document.getElementById("mcp-cancel-btn");
const mcpSaveBtn = document.getElementById("mcp-save-btn");
const mcpConfigTextarea = document.getElementById("mcp-config-textarea");

// Token & Context Spacing/Indicator
const chatMessageCountBadge = document.getElementById("chat-message-count-badge");

let currentChatId = null;
let isTypingActive = false;
let isWebSearchEnabled = false;
let selectedFiles = [];
let currentChatMessages = [];

// 🛠️ Thai-friendly Toast Notification System with Slide animation
function showToast(message, type = "success") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let icon = "✓";
    if (type === "error") {
        icon = "⚠️";
    }

    toast.innerHTML = `
        <span style="font-size:16px;">${icon}</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("toast-fade-out");
        setTimeout(() => {
            toast.remove();
        }, 200);
    }, 4000);
}

// Update the Top Bar messages indicator badge
function updateMessageCountBadge() {
    if (!chatMessageCountBadge) return;
    const count = currentChatMessages.length;
    chatMessageCountBadge.textContent = `${count} ข้อความ`;
    if (count === 0) {
        chatMessageCountBadge.classList.add("hidden");
    } else {
        chatMessageCountBadge.classList.remove("hidden");
    }
}

// Save active session state to localStorage
function saveChatToLocalStorage() {
    localStorage.setItem("myagent_chat_history", JSON.stringify(currentChatMessages));
    localStorage.setItem("myagent_chat_id", currentChatId || "");
    localStorage.setItem("myagent_chat_title", chatTitle.textContent || "ChatGPT 4o");
    updateMessageCountBadge();
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
        updateMessageCountBadge();
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
                showToast("อัปโหลดไฟล์ลงใน Workspace สำเร็จ!", "success");
            } else {
                showToast(`ไม่สามารถอัปโหลดไฟล์ได้: ${data.detail || "ข้อผิดพลาดระบบ"}`, "error");
            }
        } catch (err) {
            console.error(err);
            showToast("เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์", "error");
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
            showToast("กรุณากรอก GitHub Personal Access Token", "error");
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
                showToast("เชื่อมต่อบัญชี GitHub สำเร็จ!", "success");
            } else {
                showToast("ไม่สามารถดึงข้อมูล Repositories ได้ ตรวจสอบ Token ของคุณอีกครั้ง", "error");
            }
        } catch (err) {
            console.error(err);
            githubConnectBtn.textContent = "Connect GitHub Account";
            githubConnectBtn.disabled = false;
            showToast("เชื่อมต่อเซิร์ฟเวอร์หลักล้มเหลว", "error");
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
                showToast(`โคลน Repository "${repoName}" ลงใน Workspace สำเร็จ!`, "success");

                // Automatically notify the AI agent with a system hidden message to update context
                setTimeout(() => {
                    input.value = `[SYSTEM]: Repository ${repoName} has been imported to workspace directory successfully.`;
                    sendMessage();
                }, 800);
            } else {
                showToast(data.message || "โคลน Repository ล้มเหลว", "error");
            }
        } catch (err) {
            console.error(err);
            githubImportSubmitBtn.textContent = "Clone Repo into Workspace";
            githubImportSubmitBtn.disabled = false;
            showToast("เกิดข้อผิดพลาดในการส่งข้อมูลโคลนเซิร์ฟเวอร์", "error");
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

// Helper to determine operation category for workflow badge color-coding
function getOperationCategory(text) {
    const lower = text.toLowerCase();
    if (lower.includes("git clone") || lower.includes("cloning repository") || lower.includes("checking out branch") || lower.includes("pulling updates") || lower.includes("git status") || lower.includes("checking git status")) {
        return { class: "op-git", label: "GIT" };
    }
    if (lower.includes("reading file") || lower.includes("updating code") || lower.includes("patching file") || lower.includes("write_file") || lower.includes("read_file")) {
        return { class: "op-file", label: "FILE" };
    }
    if (lower.includes("running command") || lower.includes("running script") || lower.includes("executing") || lower.includes("command")) {
        return { class: "op-terminal", label: "EXEC" };
    }
    return { class: "op-thinking", label: "THINK" };
}

// 🛠️ Redesigned Helper to render real-time collapsible Execution thought drawer
function updateWorkflowStatus(aiTextBody, text) {
    let drawer = aiTextBody.querySelector(".workflow-drawer");
    if (!drawer) {
        drawer = document.createElement("div");
        drawer.className = "workflow-drawer";
        drawer.innerHTML = `
            <div class="workflow-drawer-header">
                <div class="workflow-drawer-header-left">
                    <span class="workflow-badge op-thinking">
                        <span class="status-pulse-dot"></span>
                        <span class="workflow-badge-label">THINK</span>
                    </span>
                    <span class="workflow-text">Thinking / Processing...</span>
                </div>
                <div class="workflow-chevron">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="6 9 12 15 18 9"></polyline>
                    </svg>
                </div>
            </div>
            <div class="workflow-details">
                <ul class="workflow-timeline"></ul>
            </div>
        `;

        aiTextBody.appendChild(drawer);

        // Expansion toggle
        const header = drawer.querySelector(".workflow-drawer-header");
        const details = drawer.querySelector(".workflow-details");
        const chevron = drawer.querySelector(".workflow-chevron");
        header.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            details.classList.toggle("expanded");
            chevron.classList.toggle("expanded");
        };
    }

    const details = drawer.querySelector(".workflow-details");
    const badge = drawer.querySelector(".workflow-badge");
    const badgeLabel = drawer.querySelector(".workflow-badge-label");
    const textLabel = drawer.querySelector(".workflow-text");
    const timeline = drawer.querySelector(".workflow-timeline");

    const category = getOperationCategory(text);

    badge.className = `workflow-badge ${category.class}`;
    badgeLabel.textContent = category.label;
    textLabel.textContent = text;
    textLabel.title = text;

    // Add unique step to timeline logs
    const existingItems = Array.from(timeline.querySelectorAll(".workflow-timeline-item-text"));
    const isDuplicate = existingItems.some(item => item.textContent === text);

    if (!isDuplicate) {
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        const li = document.createElement("li");
        li.className = "workflow-timeline-item";
        li.innerHTML = `
            <span class="workflow-timeline-item-time">${timeStr}</span>
            <span class="workflow-timeline-item-text"></span>
        `;
        li.querySelector(".workflow-timeline-item-text").textContent = text;
        timeline.appendChild(li);

        details.scrollTop = details.scrollHeight;
    }

    chatBox.scrollTop = chatBox.scrollHeight;
}

// 🛠️ Transition active pulsing workflow badge into compact Completed indicator on success
function completeWorkflowStatus(aiTextBody) {
    const drawer = aiTextBody.querySelector(".workflow-drawer");
    if (!drawer) return;

    const badge = drawer.querySelector(".workflow-badge");
    const badgeLabel = drawer.querySelector(".workflow-badge-label");
    const textLabel = drawer.querySelector(".workflow-text");
    const details = drawer.querySelector(".workflow-details");
    const chevron = drawer.querySelector(".workflow-chevron");
    const pulseDot = drawer.querySelector(".status-pulse-dot");

    badge.className = "workflow-badge op-completed";
    badgeLabel.textContent = "DONE";
    if (pulseDot) pulseDot.remove();

    textLabel.textContent = "Execution completed successfully";

    // Automatically collapse detailed steps
    details.classList.remove("expanded");
    chevron.classList.remove("expanded");
}

// MCP modal settings trigger
if (toggleMcpBtn && mcpModal) {
    toggleMcpBtn.onclick = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        mcpModal.classList.remove("hidden");

        // Fetch active configuration from backend
        try {
            const resp = await fetch(`${API_BASE}/api/mcp/config`);
            const data = await resp.json();
            mcpConfigTextarea.value = JSON.stringify(data, null, 2);
        } catch (err) {
            console.error(err);
            mcpConfigTextarea.value = '{\n  "mcpServers": {}\n}';
        }
    };
}

if (mcpCloseBtn && mcpCancelBtn && mcpModal) {
    const closeMcp = () => { mcpModal.classList.add("hidden"); };
    mcpCloseBtn.onclick = closeMcp;
    mcpCancelBtn.onclick = closeMcp;
}

if (mcpSaveBtn) {
    mcpSaveBtn.onclick = async () => {
        const rawText = mcpConfigTextarea.value.trim();

        // Quick frontend JSON parsing check
        try {
            JSON.parse(rawText);
        } catch (e) {
            showToast(`โครงสร้าง JSON ไม่ถูกต้อง: ${e.message}`, "error");
            return;
        }

        mcpSaveBtn.textContent = "Saving...";
        mcpSaveBtn.disabled = true;

        try {
            const resp = await fetch(`${API_BASE}/api/mcp/config`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    config_raw: rawText
                })
            });
            const data = await resp.json();
            mcpSaveBtn.textContent = "Save Config";
            mcpSaveBtn.disabled = false;

            if (resp.status === 200 || data.status === "success") {
                mcpModal.classList.add("hidden");
                showToast("บันทึกการตั้งค่า MCP Server สำเร็จ!", "success");
            } else {
                showToast(`ไม่สามารถบันทึกได้: ${data.detail || "ข้อผิดพลาดระบบ"}`, "error");
            }
        } catch (err) {
            console.error(err);
            mcpSaveBtn.textContent = "Save Config";
            mcpSaveBtn.disabled = false;
            showToast("ไม่สามารถเชื่อมต่อเพื่อบันทึกได้", "error");
        }
    };
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

    // Retrieve active Supabase session and access token if client is initialized
    let hasSupabaseSession = false;
    let supabaseAccessToken = "";
    if (window.supabaseInstance) {
        try {
            const { data: { session } } = await window.supabaseInstance.auth.getSession();
            if (session && session.access_token) {
                hasSupabaseSession = true;
                supabaseAccessToken = session.access_token;

                // Requirement 1 & 3: Submit prompt to Supabase prompts table (Edge Function or direct client insert)
                if (window.NEXT_PUBLIC_API_URL) {
                    try {
                        const edgeResponse = await fetch(window.NEXT_PUBLIC_API_URL, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                                "Authorization": `Bearer ${supabaseAccessToken}`
                            },
                            body: JSON.stringify({ prompt: text })
                        });
                        if (edgeResponse.ok) {
                            console.log("Successfully inserted prompt to Supabase prompts table via Edge Function API.");
                        } else {
                            const errBody = await edgeResponse.json();
                            console.error("Failed to insert prompt via Edge Function API:", errBody);
                        }
                    } catch (err) {
                        console.error("Exception when calling Edge Function API:", err);
                    }
                } else {
                    // Fallback: Direct Client Insert without non-existent 'prompt' column
                    const { error: insertError } = await window.supabaseInstance.from('prompts').insert([{
                        content: text,
                        user_id: session.user.id
                    }]);
                    if (insertError) {
                        console.error("Error inserting prompt to Supabase prompts table directly:", insertError);
                    } else {
                        console.log("Successfully inserted prompt to Supabase prompts table directly.");
                    }
                }
            }
        } catch (err) {
            console.error("Error retrieving Supabase session in sendMessage:", err);
        }
    }

    try {
        let response;
        const endpoint = `${window.NEXT_PUBLIC_API_URL || API_BASE || ""}/chat`;

        if (hasSupabaseSession && selectedFiles.length === 0) {
            // Send JSON payload directly as requested in Requirement 3
            const headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Authorization": `Bearer ${supabaseAccessToken}`
            };
            const payload = {
                "prompt": text,
                "search_web": isWebSearchEnabled
            };
            if (currentChatId) {
                payload["chat_id"] = currentChatId;
            }
            response = await fetch(endpoint, {
                method: "POST",
                headers: headers,
                body: JSON.stringify(payload)
            });
        } else {
            // Standard form-data payload with auth header if logged in
            const headers = {
                "Accept": "text/event-stream"
            };
            if (supabaseAccessToken) {
                headers["Authorization"] = `Bearer ${supabaseAccessToken}`;
            }
            response = await fetch(endpoint, {
                method: "POST",
                headers: headers,
                body: formData
            });
        }

        toggleTyping(false);

        const aiTextBody = createMessageLayout("ai");
        updateWorkflowStatus(aiTextBody, "Thinking / Processing... ");

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
                            completeWorkflowStatus(aiTextBody);

                            if (data.chat_id) currentChatId = data.chat_id;
                            if (data.title) chatTitle.textContent = data.title;

                            finalReplyText = data.reply;
                            finalModel = data.model;
                            finalTokens = data.total_tokens;
                        } else if (data.type === "error") {
                            const badge = aiTextBody.querySelector(".workflow-badge");
                            const badgeLabel = aiTextBody.querySelector(".workflow-badge-label");
                            const textLabel = aiTextBody.querySelector(".workflow-text");
                            const pulseDot = aiTextBody.querySelector(".status-pulse-dot");
                            if (badge) {
                                badge.className = "workflow-badge";
                                badge.style.backgroundColor = "#ef4444";
                                badgeLabel.textContent = "FAIL";
                                if (pulseDot) pulseDot.remove();
                                textLabel.textContent = `Error: ${data.message}`;
                            } else {
                                aiTextBody.textContent = `⚠️ Error: ${data.message}`;
                            }
                            showToast(`ระบบติดขัด: ${data.message}`, "error");
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
        showToast("ขาดการเชื่อมต่อสายธารข้อมูลหลังบ้าน", "error");
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
        if (!res.ok) {
            console.warn(`Failed to fetch chats history list: HTTP ${res.status}`);
            return;
        }
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            console.warn("Chats list endpoint did not return JSON payload.");
            return;
        }
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
    try {
        const res = await fetch(`${API_BASE}/chats/${cId}`);
        if (!res.ok) {
            console.error(`Failed to fetch chat session ${cId}: HTTP ${res.status}`);
            return;
        }
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            console.error("Chats detail endpoint did not return JSON payload.");
            return;
        }
        const d = await res.json();
        chatTitle.textContent = d.title;
        currentChatMessages = d.messages || [];
        currentChatMessages.forEach(m => renderStaticMessage(m.role, m.content, m.model, m.total_tokens));
        saveChatToLocalStorage();
    } catch (err) {
        console.error("Error inside switchChatSession:", err);
    }
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

async function loadMemoriesList() {
    try {
        const res = await fetch(`${API_BASE}/memory`);
        if (!res.ok) {
            console.warn(`Failed to fetch memories: HTTP ${res.status}`);
            return;
        }
        const contentType = res.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
            console.warn("Memories endpoint did not return JSON payload.");
            return;
        }
        const d = await res.json();
        memoryList.innerHTML = d.memories.length === 0 ? "<li>No memory</li>" : "";
        d.memories.forEach((f, i) => {
            const li = document.createElement("li");
            li.className = "memory-item";
            li.innerHTML = `<span>${f}</span><button class="memory-delete-btn pop-btn" onclick="deleteMemoryFact(${i})">🗑️</button>`;
            memoryList.appendChild(li);
        });
    } catch (e) {
        console.error("Error in loadMemoriesList:", e);
    }
}
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

// Initialize Supabase Client if env variables are available
let supabaseClient = null;
const supabaseUrl = window.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = window.NEXT_PUBLIC_SUPABASE_ANON_KEY;

function isValidHttpUrl(string) {
    if (!string || typeof string !== "string") return false;
    if (string.includes("{{") || string.includes("}}")) return false;
    try {
        const url = new URL(string);
        return url.protocol === "http:" || url.protocol === "https:";
    } catch (_) {
        return false;
    }
}

if (isValidHttpUrl(supabaseUrl) && supabaseAnonKey && !supabaseAnonKey.includes("{{") && typeof supabase !== 'undefined') {
    try {
        supabaseClient = supabase.createClient(supabaseUrl, supabaseAnonKey);
        window.supabaseInstance = supabaseClient;
        console.log("Supabase Client successfully initialized from Edge config.");
    } catch (err) {
        console.error("Failed to initialize Supabase Client:", err);
    }
} else {
    console.log("Supabase Client initialization skipped: Invalid URL or missing/template keys.");
}

// GitHub Authentication Functions using Supabase Client
async function signInWithGitHub() {
    if (!supabaseClient) {
        console.error("Supabase client is not initialized.");
        return;
    }
    try {
        const { data, error } = await supabaseClient.auth.signInWithOAuth({
            provider: 'github',
            options: {
                redirectTo: window.location.origin
            }
        });
        if (error) throw error;
    } catch (err) {
        console.error("Supabase sign in with GitHub error:", err);
        showToast("มีข้อผิดพลาดในการเข้าสู่ระบบด้วย GitHub", "error");
    }
}

async function signOut() {
    if (!supabaseClient) {
        console.error("Supabase client is not initialized.");
        return;
    }
    try {
        const { error } = await supabaseClient.auth.signOut();
        if (error) throw error;
        showToast("ออกจากระบบ GitHub เรียบร้อยแล้ว", "success");
        setTimeout(() => {
            window.location.reload();
        }, 1000);
    } catch (err) {
        console.error("Supabase sign out error:", err);
        showToast("มีข้อผิดพลาดในการออกจากระบบ", "error");
    }
}

// Helper to render message with custom metadata (avatar and name) in real-time timeline
async function renderStaticMessageWithMetadata(authorName, authorAvatar, promptText) {
    const rowDiv = document.createElement("div");
    rowDiv.className = "message-row user-row";
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";

    const avatarEl = document.createElement("div");
    avatarEl.className = "avatar";
    if (authorAvatar) {
        avatarEl.innerHTML = `<img src="${authorAvatar}" alt="${authorName}" style="width:100%; height:100%; border-radius:50%; object-fit:cover;">`;
    } else {
        avatarEl.textContent = authorName ? authorName.charAt(0).toUpperCase() : "U";
    }

    const textBody = document.createElement("div");
    textBody.className = "text-body";

    const nameLabel = document.createElement("strong");
    nameLabel.style.display = "block";
    nameLabel.style.fontSize = "12px";
    nameLabel.style.color = "var(--text-muted)";
    nameLabel.style.marginBottom = "4px";
    nameLabel.textContent = authorName || "GitHub User";

    const contentText = document.createElement("div");
    contentText.textContent = promptText;

    textBody.appendChild(nameLabel);
    textBody.appendChild(contentText);
    contentDiv.appendChild(avatarEl);
    contentDiv.appendChild(textBody);
    rowDiv.appendChild(contentDiv);
    chatBox.appendChild(rowDiv);

    chatBox.scrollTop = chatBox.scrollHeight;
}

// Fetch all prompts from public.prompts including user metadata
async function loadAllPromptsFromSupabase() {
    if (!supabaseClient) return;
    try {
        const { data, error } = await supabaseClient
            .from('prompts')
            .select('id, content, created_at, user_id, users (username, avatar_url)')
            .order('created_at', { ascending: true });

        if (error) {
            console.error("Error fetching prompts from Supabase public.prompts:", error);
            return;
        }

        if (data && data.length > 0) {
            chatBox.innerHTML = "";
            data.forEach(item => {
                const authorName = item.users?.username || "GitHub User";
                const authorAvatar = item.users?.avatar_url || "";
                const promptText = item.content || "";
                renderStaticMessageWithMetadata(authorName, authorAvatar, promptText);
            });
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    } catch (err) {
        console.error("Exception in loadAllPromptsFromSupabase:", err);
    }
}

// Enable Supabase Realtime subscription on public.prompts table
function setupPromptsRealtimeSubscription() {
    if (!supabaseClient) return;
    try {
        const channel = supabaseClient
            .channel('schema-db-changes')
            .on(
                'postgres_changes',
                {
                    event: 'INSERT',
                    schema: 'public',
                    table: 'prompts'
                },
                async (payload) => {
                    console.log('Realtime INSERT received on public.prompts:', payload);
                    const newRow = payload.new;
                    if (newRow) {
                        try {
                            // Avoid double-rendering our own message if we are the sender
                            const { data: { session } } = await supabaseClient.auth.getSession();
                            if (session && session.user && session.user.id === newRow.user_id) {
                                console.log("Skipping realtime rendering of our own inserted prompt to avoid duplicates.");
                                return;
                            }

                            const { data: userData, error } = await supabaseClient
                                .from('users')
                                .select('username, avatar_url')
                                .eq('id', newRow.user_id)
                                .single();

                            const authorName = userData?.username || "GitHub User";
                            const authorAvatar = userData?.avatar_url || "";
                            const promptText = newRow.content || "";

                            renderStaticMessageWithMetadata(authorName, authorAvatar, promptText);
                        } catch (userErr) {
                            console.error("Error loading user metadata in Realtime callback:", userErr);
                            renderStaticMessageWithMetadata("GitHub User", "", newRow.content || "");
                        }
                    }
                }
            )
            .subscribe();
    } catch (err) {
        console.error("Failed to enable Supabase Realtime subscription:", err);
    }
}

// GitHub User Authentication session handling and element binding
async function initAuthSession() {
    const authLoading = document.getElementById("auth-loading");
    const authGuest = document.getElementById("auth-guest");
    const authUser = document.getElementById("auth-user");
    const userAvatar = document.getElementById("user-avatar");
    const userUsername = document.getElementById("user-username");
    const userEmail = document.getElementById("user-email");
    const githubSigninBtn = document.getElementById("github-signin-btn");
    const logoutBtn = document.getElementById("logout-btn");

    if (!authLoading || !authGuest || !authUser) return;

    // 1. If Supabase Client is initialized, check session state and bind OAuth sign-in / sign-out
    if (supabaseClient) {
        if (githubSigninBtn) {
            // Remove traditional redirection and bind signInWithGitHub
            githubSigninBtn.removeAttribute("href");
            githubSigninBtn.style.cursor = "pointer";
            githubSigninBtn.onclick = async (e) => {
                e.preventDefault();
                await signInWithGitHub();
            };
        }

        if (logoutBtn) {
            logoutBtn.onclick = async (e) => {
                e.preventDefault();
                await signOut();
            };
        }

        try {
            const { data: { session }, error } = await supabaseClient.auth.getSession();
            if (error) throw error;
            if (session && session.user) {
                // User is authenticated via Supabase session
                const user = session.user;
                if (userAvatar) {
                    userAvatar.src = user.user_metadata?.avatar_url || "https://github.com/identicons/guest.png";
                }
                if (userUsername) {
                    userUsername.textContent = user.user_metadata?.full_name || user.user_metadata?.user_name || "GitHub User";
                }
                if (userEmail) {
                    userEmail.textContent = user.email || "";
                }

                authLoading.classList.add("hidden");
                authGuest.classList.add("hidden");
                authUser.classList.remove("hidden");

                // Connect UI to Supabase Prompts feed and enable realtime updates
                loadAllPromptsFromSupabase();
                setupPromptsRealtimeSubscription();

                return;
            }
        } catch (err) {
            console.error("Error retrieving Supabase auth session:", err);
        }
    } else {
        // 2. Fallback: Use backend-managed cookie session check
        if (githubSigninBtn) {
            githubSigninBtn.href = `${API_BASE || ""}/auth/github/login`;
        }
        if (logoutBtn) {
            logoutBtn.onclick = async (e) => {
                e.preventDefault();
                try {
                    const response = await fetch(`${API_BASE || ""}/auth/logout`);
                    if (response.ok || response.redirected) {
                        showToast("ออกจากระบบ GitHub เรียบร้อยแล้ว", "success");
                        setTimeout(() => {
                            window.location.reload();
                        }, 1000);
                    } else {
                        showToast("มีข้อผิดพลาดในการออกจากระบบ", "error");
                    }
                } catch (err) {
                    console.error("Logout request failed:", err);
                    showToast("มีข้อผิดพลาดในการเชื่อมต่อเครือข่าย", "error");
                }
            };
        }

        try {
            const response = await fetch(`${API_BASE || ""}/auth/me`);
            if (response.ok) {
                const userData = await response.json();
                if (userData && (userData.github_id || userData.username)) {
                    // User is authenticated successfully
                    if (userAvatar) {
                        userAvatar.src = userData.avatar_url || "https://github.com/identicons/guest.png";
                    }
                    if (userUsername) {
                        userUsername.textContent = userData.name || userData.username || "GitHub User";
                    }
                    if (userEmail) {
                        userEmail.textContent = userData.email || `@${userData.username || "user"}`;
                    }

                    authLoading.classList.add("hidden");
                    authGuest.classList.add("hidden");
                    authUser.classList.remove("hidden");
                    return;
                }
            }
        } catch (err) {
            console.error("Error verifying active GitHub login session:", err);
        }
    }

    // Default: Not authenticated (Guest state)
    authLoading.classList.add("hidden");
    authUser.classList.add("hidden");
    authGuest.classList.remove("hidden");
}

loadChatHistoryList();
loadChatFromLocalStorage();
initAuthSession();
