const BASE_URL = "https://myagent-807h.onrender.com";
const API_TOKEN = "super-secret-ide-agent-token-123"; // ให้ตรงกับ backend

export const sendMessageToAgent = async (message, chatId = null) => {
  try {
    const response = await fetch(`${BASE_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Token": API_TOKEN,
      },
      body: JSON.stringify({
        message: message,
        chat_id: chatId,
      }),
    });

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("API Error:", error);
    throw error;
  }
};