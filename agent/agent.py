import os
import httpx
import json
from agent.tools import (
    read_file_tool, write_file_tool, list_directory_tool,
    patch_file_tool, view_dir_tool, execute_command_tool,
    clone_repository_tool, git_status_tool, git_rollback_tool,
    git_checkout_tool, git_pull_tool
)

class ChatAgent:
    def __init__(self):
        # รวบรวม API Keys จากค่ายต่างๆ (หยิบจาก Environment หรือวางคีย์ดิบลงตรงนี้ได้เลย)
        self.groq_key = os.getenv("GROQ_API_KEY", "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")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6LMjtehi8snLtEjfb2JGB4sTC_YtKxudpKm-jg3A3Fguw")
        self.openai_key = os.getenv("OPENAI_API_KEY", "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")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "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")

    async def get_response(self, prompt: str, status_callback=None) -> dict:
        """ระบบสลับสมองข้ามค่ายอัตโนมัติพร้อมระบบ Tool Calling (Function Calling) ของ Groq และ OpenAI"""
        
        async def trigger_status(msg: str):
            if status_callback:
                try:
                    await status_callback(msg)
                except Exception:
                    pass

        await trigger_status("Thinking / Processing...")

        system_message = {
            "role": "system",
            "content": (
                "คุณคือ AI IDE Agent ที่มี Tools สำหรับจัดการไฟล์และ Git "
                "หากผู้ใช้สั่งให้ Clone Repo, อ่านไฟล์, หรือดูรายชื่อไฟล์ คุณต้องเรียกใช้ Tool "
                "(`git_clone`, `list_directory`, `read_file`, `patch_file`, `write_file`, `execute_command`) จริงๆ เท่านั้น "
                "**ห้ามเขียนคำอธิบายคำสั่ง Terminal หรือจำลองผลลัพธ์ขึ้นมาเองเด็ดขาด** "
                "คุณมีสิทธิ์เข้าถึง ทำงาน แก้ไข อ่าน และจัดการไฟล์ต่าง ๆ ใน Workspace ผ่านเครื่องมือ (Tools) ที่มีให้ครบถ้วน "
                "หลังจากรันเครื่องมือเสร็จเรียบร้อยและได้รับผลลัพธ์แล้ว ให้สรุปคำตอบให้ผู้ใช้อย่างชัดเจน ถูกต้อง และเป็นมิตร"
            )
        }

        user_message = {"role": "user", "content": prompt}
        messages = [system_message, user_message]

        tools_schema = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Reads the content of a file relative to the workspace directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The relative path to the file inside the workspace."
                            }
                        },
                        "required": ["filepath"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Writes or overwrites a file inside the workspace entirely with the given content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The relative path to the file inside the workspace."
                            },
                            "content": {
                                "type": "string",
                                "description": "The complete text content to write into the file."
                            }
                        },
                        "required": ["filepath", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "Lists directory structure and contents in the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "The directory path to list. Defaults to '.' (workspace root).",
                                "default": "."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "patch_file",
                    "description": "Patches an existing file by replacing a search_block with replace_block.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {
                                "type": "string",
                                "description": "The relative path to the file to patch."
                            },
                            "search_block": {
                                "type": "string",
                                "description": "The exact block of code to search for."
                            },
                            "replace_block": {
                                "type": "string",
                                "description": "The block of code to replace it with."
                            }
                        },
                        "required": ["filepath", "search_block", "replace_block"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "view_dir",
                    "description": "Recursively lists folders and files in the workspace directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "The relative path to scan.",
                                "default": "."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_command",
                    "description": "Executes a shell command inside the workspace directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The terminal command to run."
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_clone",
                    "description": "Clones a remote git repository into the workspace directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "repo_url": {
                                "type": "string",
                                "description": "The GitHub repository URL to clone."
                            }
                        },
                        "required": ["repo_url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_status",
                    "description": "Checks the current modified, added, or deleted files in the git workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_checkout",
                    "description": "Switches to an existing git branch or creates a new one.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "branch_name": {
                                "type": "string",
                                "description": "The name of the branch to switch to or create."
                            }
                        },
                        "required": ["branch_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "git_pull",
                    "description": "Pulls the latest updates from the remote repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            }
        ]

        # Map tool names to Python functions
        def execute_local_tool(name: str, args: dict) -> dict:
            try:
                if name == "read_file":
                    return read_file_tool(args.get("filepath", ""))
                elif name == "write_file":
                    return write_file_tool(args.get("filepath", ""), args.get("content", ""))
                elif name == "list_directory":
                    return list_directory_tool(args.get("path", "."))
                elif name == "patch_file":
                    return patch_file_tool(
                        args.get("filepath", ""),
                        args.get("search_block", ""),
                        args.get("replace_block", "")
                    )
                elif name == "view_dir":
                    return view_dir_tool(args.get("path", "."))
                elif name == "execute_command":
                    return execute_command_tool(args.get("command", ""))
                elif name == "git_clone" or name == "clone_repository":
                    return clone_repository_tool(args.get("repo_url", ""))
                elif name == "git_status":
                    return git_status_tool()
                elif name == "git_checkout":
                    return git_checkout_tool(args.get("branch_name", ""))
                elif name == "git_pull":
                    return git_pull_tool()
                else:
                    return {"status": "error", "message": f"Unknown tool: {name}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        # --- ลำดับที่ 1: ใช้ Groq เป็นหลักพร้อมการรัน Tool (Tool Execution Loop) ---
        if self.groq_key and "คีย์_" not in self.groq_key:
            try:
                max_turns = 10
                current_messages = list(messages)
                total_tokens = 0

                async with httpx.AsyncClient(timeout=30.0) as client:
                    for turn in range(max_turns):
                        payload = {
                            "model": "llama-3.3-70b-versatile",
                            "messages": current_messages,
                            "tools": tools_schema,
                            "tool_choice": "auto",
                            "temperature": 0.5
                        }

                        response = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.groq_key}",
                                "Content-Type": "application/json"
                            },
                            json=payload
                        )

                        if response.status_code == 200:
                            result = response.json()
                            total_tokens += result.get("usage", {}).get("total_tokens", 0)
                            message_resp = result["choices"][0]["message"]

                            # Append assistant message to history
                            current_messages.append(message_resp)

                            tool_calls = message_resp.get("tool_calls")
                            if tool_calls:
                                for tool_call in tool_calls:
                                    tool_name = tool_call["function"]["name"]
                                    raw_args = tool_call["function"]["arguments"]

                                    # Parse arguments safely
                                    if isinstance(raw_args, str):
                                        try:
                                            parsed_args = json.loads(raw_args)
                                        except Exception:
                                            parsed_args = {}
                                    else:
                                        parsed_args = raw_args or {}

                                    # Provide dynamic progress/workflow status updates before invoking the tool
                                    if tool_name == "read_file":
                                        await trigger_status(f"Reading file: {parsed_args.get('filepath', '')}...")
                                    elif tool_name == "write_file":
                                        await trigger_status(f"Updating code: {parsed_args.get('filepath', '')}...")
                                    elif tool_name == "patch_file":
                                        await trigger_status(f"Patching file: {parsed_args.get('filepath', '')}...")
                                    elif tool_name == "execute_command":
                                        await trigger_status(f"Running command: {parsed_args.get('command', '')}...")
                                    elif tool_name == "git_clone" or tool_name == "clone_repository":
                                        await trigger_status(f"Git cloning repository: {parsed_args.get('repo_url', '')}...")
                                    elif tool_name == "git_checkout":
                                        await trigger_status(f"Git checking out branch: {parsed_args.get('branch_name', '')}...")
                                    elif tool_name == "git_pull":
                                        await trigger_status("Git pulling updates...")
                                    elif tool_name == "git_status":
                                        await trigger_status("Checking git status...")
                                    else:
                                        await trigger_status(f"Running tool {tool_name}...")

                                    # Execute the tool
                                    tool_output = execute_local_tool(tool_name, parsed_args)

                                    # Append tool result to messages
                                    current_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call["id"],
                                        "name": tool_name,
                                        "content": json.dumps(tool_output, ensure_ascii=False)
                                    })
                                # Continue the loop to let Groq process tool output
                                continue
                            else:
                                # No tool calls, we have the final content
                                return {
                                    "reply": message_resp.get("content") or "",
                                    "model": "Groq (Llama-3.3-70b)",
                                    "total_tokens": total_tokens
                                }
                        else:
                            print(f"[Brain Switcher]: Groq ติดปัญหา (Code {response.status_code}) กำลังส่งงานให้ Gemini ทำแทน...")
                            break
            except Exception as e:
                print(f"[Brain Switcher]: Groq เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 2: สลับไปใช้ Google Gemini อัตโนมัติ ---
        if self.gemini_key and "คีย์_" not in self.gemini_key:
            try:
                # Use gemini-2.5-flash as requested in memory guidelines
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
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
                            "model": "Google Gemini 2.5 Flash",
                            "total_tokens": 0
                        }
                    else:
                        print(f"[Brain Switcher]: Gemini ติดปัญหา (Code {response.status_code}) กำลังส่งงานให้ OpenAI ทำแทน...")
            except Exception as e:
                print(f"[Brain Switcher]: Gemini เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 3: สลับไปใช้ OpenAI (GPT-4o-Mini) พร้อมระบบ Tool Calling สำรอง ---
        if self.openai_key and "คีย์_" not in self.openai_key:
            try:
                max_turns = 10
                current_messages = list(messages)
                total_tokens = 0

                async with httpx.AsyncClient(timeout=30.0) as client:
                    for turn in range(max_turns):
                        payload = {
                            "model": "gpt-4o-mini",
                            "messages": current_messages,
                            "tools": tools_schema,
                            "tool_choice": "auto",
                            "temperature": 0.5
                        }

                        response = await client.post(
                            "https://api.openai.com/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.openai_key}",
                                "Content-Type": "application/json"
                            },
                            json=payload
                        )

                        if response.status_code == 200:
                            result = response.json()
                            total_tokens += result.get("usage", {}).get("total_tokens", 0)
                            message_resp = result["choices"][0]["message"]

                            # Append assistant message to history
                            current_messages.append(message_resp)

                            tool_calls = message_resp.get("tool_calls")
                            if tool_calls:
                                for tool_call in tool_calls:
                                    tool_name = tool_call["function"]["name"]
                                    raw_args = tool_call["function"]["arguments"]

                                    # Parse arguments safely
                                    if isinstance(raw_args, str):
                                        try:
                                            parsed_args = json.loads(raw_args)
                                        except Exception:
                                            parsed_args = {}
                                    else:
                                        parsed_args = raw_args or {}

                                    # Provide dynamic progress/workflow status updates before invoking the tool (OpenAI fallback)
                                    if tool_name == "read_file":
                                        await trigger_status(f"Reading file: {parsed_args.get('filepath', '')}...")
                                    elif tool_name == "write_file":
                                        await trigger_status(f"Updating code: {parsed_args.get('filepath', '')}...")
                                    elif tool_name == "patch_file":
                                        await trigger_status(f"Patching file: {parsed_args.get('filepath', '')}...")
                                    elif tool_name == "execute_command":
                                        await trigger_status(f"Running command: {parsed_args.get('command', '')}...")
                                    elif tool_name == "git_clone" or tool_name == "clone_repository":
                                        await trigger_status(f"Git cloning repository: {parsed_args.get('repo_url', '')}...")
                                    elif tool_name == "git_checkout":
                                        await trigger_status(f"Git checking out branch: {parsed_args.get('branch_name', '')}...")
                                    elif tool_name == "git_pull":
                                        await trigger_status("Git pulling updates...")
                                    elif tool_name == "git_status":
                                        await trigger_status("Checking git status...")
                                    else:
                                        await trigger_status(f"Running tool {tool_name}...")

                                    # Execute the tool
                                    tool_output = execute_local_tool(tool_name, parsed_args)

                                    # Append tool result to messages
                                    current_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call["id"],
                                        "name": tool_name,
                                        "content": json.dumps(tool_output, ensure_ascii=False)
                                    })
                                # Continue loop
                                continue
                            else:
                                # No tool calls, return final response
                                return {
                                    "reply": message_resp.get("content") or "",
                                    "model": "OpenAI (GPT-4o-Mini)",
                                    "total_tokens": total_tokens
                                }
                        else:
                            print(f"[Brain Switcher]: OpenAI ติดปัญหา (Code {response.status_code}) กำลังส่งงานให้ OpenRouter ทำแทน...")
                            break
            except Exception as e:
                print(f"[Brain Switcher]: OpenAI เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 4: ด่านสุดท้ายสลับไปใช้ OpenRouter (Auto-Free Models / openrouter/free) ---
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
                            "model": "openrouter/free", # Use openrouter/free model from memory guidelines
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.7
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return {
                            "reply": result["choices"][0]["message"]["content"],
                            "model": "OpenRouter (Free)",
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
