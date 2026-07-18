const input = document.getElementById("message-input");
const button = document.getElementById("send-button");
const chat = document.getElementById("chat-box");

async function sendMessage() {
    const text = input.value.trim();
    if (text === "") return;

    // Display user input message
    const user = document.createElement("div");
    user.className = "message user";
    user.textContent = text;
    chat.appendChild(user);

    input.value = "";
    chat.scrollTop = chat.scrollHeight;

    try {
        // Post text packet block directly to FastAPI handler
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        // Prepare context for Markdown Rendering
        const ai = document.createElement("div");
        ai.className = "message ai markdown-body";
        ai.innerHTML = marked.parse(data.reply);

        // Run styling highlighting explicitly inside the new block component
        ai.querySelectorAll("pre code").forEach((block) => {
            hljs.highlightElement(block);
        });

        chat.appendChild(ai);
    } catch (error) {
        const errElement = document.createElement("div");
        errElement.className = "message ai error";
        errElement.textContent = "Could not sync transaction data upstream with the network server.";
        chat.appendChild(errElement);
    }

    chat.scrollTop = chat.scrollHeight;
}

button.onclick = sendMessage;

input.onkeydown = function (e) {
    if (e.key === "Enter") {
        sendMessage();
    }
};