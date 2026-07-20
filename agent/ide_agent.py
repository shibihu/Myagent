import json
from agent.agent import ChatAgent
from agent.tools import (
    read_file_tool, patch_file_tool, view_dir_tool,
    execute_command_tool, clone_repository_tool,
    git_status_tool, git_rollback_tool
)

class IDEAgent:
    def __init__(self):
        self.agent = ChatAgent()

    async def run(self, user_instruction: str, max_iterations: int = 10) -> str:
        """
        Runs an autonomous agent loop (ReAct style) where the AI receives instruction,
        determines which tool to use, sees the output, and corrects its own errors
        until the goal is completed or iteration limit is reached.
        """
        # Build the system instruction detailing the tools available.
        system_prompt = """
คุณคือ "IDE Agent" บอตผู้ช่วยเขียน รัน และทดสอบโค้ดแบบอัตโนมัติ
คุณมีสิทธิ์เข้าถึง Workspace และสามารถเรียกใช้เครื่องมือ (Tools) ต่อไปนี้เพื่อทำงานให้สำเร็จ:

1. read_file: อ่านไฟล์ใน Workspace
   - รูปแบบการเรียกใช้: {"tool": "read_file", "filepath": "เส้นทาง/ไปยัง/ไฟล์.txt"}

2. patch_file: แก้ไขโค้ดเฉพาะจุดในไฟล์แบบไม่ต้องเขียนทับทั้งไฟล์
   - หากไฟล์ไม่มีอยู่จริง และต้องการเขียนเนื้อหาใหม่ทั้งหมด ให้ตั้งค่า "search_block" เป็นค่าว่าง "" หรือ "null" หรือไม่ใส่มาเลยก็ได้
   - รูปแบบการเรียกใช้: {"tool": "patch_file", "filepath": "เส้นทาง/ไปยัง/ไฟล์.py", "search_block": "โค้ดเดิมที่จะค้นหา", "replace_block": "โค้ดใหม่ที่จะมาแทนที่"}

3. view_dir: ดูโครงสร้างโฟลเดอร์ทั้งหมด
   - รูปแบบการเรียกใช้: {"tool": "view_dir", "path": "."}

4. execute_command: สั่งรันคำสั่งใน Workspace และส่งผลลัพธ์กลับมา
   - ใช้ในการติดตั้งแพ็กเกจ รันสคริปต์ รันเทสต์ ฯลฯ
   - รูปแบบการเรียกใช้: {"tool": "execute_command", "command": "คำสั่งที่จะรัน"}

5. clone_repository: ดึง Repository จาก GitHub ลงมาใน Workspace (จะล้าง Workspace เดิมก่อนเสมอ)
   - รูปแบบการเรียกใช้: {"tool": "clone_repository", "repo_url": "ลิงก์ GitHub"}

6. git_status: เช็กความเปลี่ยนแปลงของโค้ดใน git
   - รูปแบบการเรียกใช้: {"tool": "git_status"}

7. git_rollback: ย้อนโค้ดกลับกรณีทำโค้ดพังหรือรันไม่ผ่าน
   - รูปแบบการเรียกใช้: {"tool": "git_rollback"}

คำแนะนำการตอบกลับ:
- หากคุณจำเป็นต้องเรียกใช้เครื่องมือ (Tool) ให้ตอบกลับด้วยโครงสร้าง JSON ตัวเดียวเท่านั้น ห้ามมีคำอธิบายอื่น ห้ามครอบด้วย Markdown Block (เช่น ```json) ยกเว้นถ้าคุณคิดว่านั่นคือสิ่งเดียวที่ส่งคืนได้ แต่จะดีที่สุดหากคุณตอบ JSON ตรงๆ เลย
  ตัวอย่างการเรียก Tool:
  {"tool": "execute_command", "command": "pytest"}

- หากงานสำเร็จลุล่วงแล้ว หรือคุณต้องการส่งรายงานสรุปให้ผู้ใช้ ให้ส่งข้อความปกติที่ไม่ใช่โครงสร้างการเรียกใช้ Tool โดยระบุคำว่า [DONE] หรือสรุปขั้นตอนต่างๆ ให้ชัดเจน

- หากรันโค้ดแล้วเกิด Error ให้วิเคราะห์สาเหตุ แล้วใช้เครื่องมือแก้ไขไฟล์ และสั่งรันทดสอบซ้ำอีกครั้งจนกว่าจะทำงานได้อย่างสมบูรณ์!
"""

        history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"งานที่ต้องการให้ทำ: {user_instruction}"}
        ]

        summary_report = ""

        for iteration in range(max_iterations):
            # Prompt the agent with the conversation history so far.
            # Convert history list into a single prompt for ChatAgent.get_response
            combined_prompt = ""
            for item in history:
                combined_prompt += f"\n[{item['role']}]: {item['content']}"

            combined_prompt += "\n\nกรุณาตอบกลับเป็น JSON เครื่องมือ หรือสรุปผลหากเสร็จสิ้นงานแล้ว:"

            res = await self.agent.get_response(combined_prompt)
            reply = res["reply"].strip()

            # Clean reply if agent wrapped it inside markdown blocks
            clean_reply = reply
            if reply.startswith("```"):
                # Strip leading/trailing lines with ```
                lines = reply.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_reply = "\n".join(lines).strip()

            # Try parsing as JSON to see if it's a tool call
            is_tool = False
            try:
                tool_call = json.loads(clean_reply)
                if isinstance(tool_call, dict) and "tool" in tool_call:
                    is_tool = True
                    tool_name = tool_call["tool"]
                    tool_result = {}

                    if tool_name == "read_file":
                        tool_result = read_file_tool(tool_call.get("filepath", ""))
                    elif tool_name == "patch_file":
                        tool_result = patch_file_tool(
                            tool_call.get("filepath", ""),
                            tool_call.get("search_block", ""),
                            tool_call.get("replace_block", "")
                        )
                    elif tool_name == "view_dir":
                        tool_result = view_dir_tool(tool_call.get("path", "."))
                    elif tool_name == "execute_command":
                        tool_result = execute_command_tool(tool_call.get("command", ""))
                    elif tool_name == "clone_repository":
                        tool_result = clone_repository_tool(tool_call.get("repo_url", ""))
                    elif tool_name == "git_status":
                        tool_result = git_status_tool()
                    elif tool_name == "git_rollback":
                        tool_result = git_rollback_tool()
                    else:
                        tool_result = {"status": "error", "message": f"Unknown tool '{tool_name}'"}

                    # Log the output and add it to the conversation history
                    history.append({"role": "assistant", "content": reply})
                    history.append({"role": "user", "content": f"[Tool Output for {tool_name}]: {json.dumps(tool_result, ensure_ascii=False)}"})

            except Exception:
                pass

            if not is_tool:
                # The agent returned a text report instead of a tool JSON, or it finished
                summary_report = reply
                break

        if not summary_report:
            summary_report = "⚠️ [ระบบแจ้งเตือน]: สิ้นสุดจำนวน Iteration สูงสุดแล้วแต่ยังไม่มีรายงานสรุปอย่างเป็นทางการจากบอต"

        return summary_report
