import os
import httpx

class ChatAgent:
    def __init__(self):
        # รวบรวม API Keys จากค่ายต่างๆ (หยิบจาก Environment หรือวางคีย์ดิบลงตรงนี้ได้เลย)
        self.groq_key = os.getenv("GROQ_API_KEY", "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")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6LMjtehi8snLtEjfb2JGB4sTC_YtKxudpKm-jg3A3Fguw")
        self.openai_key = os.getenv("OPENAI_API_KEY", "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")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "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")

    async def get_response(self, prompt: str) -> dict:
        """ระบบสลับสมองข้ามค่ายอัตโนมัติเมื่อค่ายใดค่ายหนึ่งล่มหรือติด Rate Limit"""
        
        # --- ลำดับที่ 1: ใช้ Groq เป็นหลัก ---
        if self.groq_key and "คีย์_" not in self.groq_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.groq_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return {
                            "reply": result["choices"][0]["message"]["content"],
                            "model": "Groq (Llama-3.3-70b)",
                            "total_tokens": result.get("usage", {}).get("total_tokens", 0)
                        }
                    else:
                        print(f"[Brain Switcher]: Groq ติดปัญหา (Code {response.status_code}) กำลังส่งงานให้ Gemini ทำแทน...")
            except Exception as e:
                print(f"[Brain Switcher]: Groq เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 2: สลับไปใช้ Google Gemini อัตโนมัติ ---
        if self.gemini_key and "คีย์_" not in self.gemini_key:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        url,
                        headers={"Content-Type": "application/json"},
                        json={
                            "contents": [{"parts": [{"text": prompt}]}]
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        reply_text = result['candidates'][0]['content']['parts'][0]['text']
                        return {
                            "reply": reply_text,
                            "model": "Google Gemini 1.5 Flash",
                            "total_tokens": 0
                        }
                    else:
                        print(f"[Brain Switcher]: Gemini ติดปัญหา (Code {response.status_code}) กำลังส่งงานให้ OpenAI ทำแทน...")
            except Exception as e:
                print(f"[Brain Switcher]: Gemini เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 3: สลับไปใช้ OpenAI (GPT-4o-Mini) ---
        if self.openai_key and "คีย์_" not in self.openai_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openai_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return {
                            "reply": result["choices"][0]["message"]["content"],
                            "model": "OpenAI (GPT-4o-Mini)",
                            "total_tokens": result.get("usage", {}).get("total_tokens", 0)
                        }
                    else:
                        print(f"[Brain Switcher]: OpenAI ติดปัญหา (Code {response.status_code}) กำลังส่งงานให้ OpenRouter ทำแทน...")
            except Exception as e:
                print(f"[Brain Switcher]: OpenAI เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 4: ด่านสุดท้ายสลับไปใช้ OpenRouter (Auto-Free Models) ---
        if self.openrouter_key and "คีย์_" not in self.openrouter_key:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.openrouter_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "openrouter/auto-free", # สุ่มเลือกโมเดลฟรีที่เจ๋งที่สุดตอนนั้นมาตอบให้เลย
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return {
                            "reply": result["choices"][0]["message"]["content"],
                            "model": "OpenRouter (Auto-Free)",
                            "total_tokens": result.get("usage", {}).get("total_tokens", 0)
                        }
            except Exception as e:
                print(f"[Brain Switcher]: OpenRouter เชื่อมต่อไม่ได้ -> {e}")

        # --- กรณีสุดท้าย: ถ้าคีย์ทั้งหมดในเครื่องไม่มี หรือล่มพร้อมกันหมด ---
        return {
            "reply": "⚠️ [ระบบขัดข้อง]: ตอนนี้ค่าย AI ทั้งหมด (Groq, Gemini, OpenAI, OpenRouter) ติดลิมิตโควตาฟรีพร้อมกันหรือคีย์ขัดข้องครับสหาย โปรดรอให้ระบบรีเซ็ตสักครู่เด็ดขาดนะครับ!",
            "model": "All Providers Exhausted",
            "total_tokens": 0
        }