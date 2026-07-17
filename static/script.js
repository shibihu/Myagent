const input = document.getElementById("message-input");

const button = document.getElementById("send-button");

const chat = document.getElementById("chat-box");

button.onclick = function(){

    const text = input.value.trim();

    if(text === "") return;

    const div = document.createElement("div");

    div.className = "message user";

    div.textContent = text;

    chat.appendChild(div);

    input.value = "";

    chat.scrollTop = chat.scrollHeight;

}