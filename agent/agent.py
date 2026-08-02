import os
from dotenv import load_dotenv
import httpx
import json
from agent.tools import (
    read_file_tool, write_file_tool, list_directory_tool,
    patch_file_tool, view_dir_tool, execute_command_tool,
    clone_repository_tool, git_status_tool, git_rollback_tool,
    git_checkout_tool, git_pull_tool
)

load_dotenv(".env.example")  # Load environment variables from .env file

def filter_thought_process(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    import re
    # Strip <thought>...</thought> tags and everything inside them
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
    # Strip <reasoning>...</reasoning> tags
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    # Strip markdown code blocks of thought if any
    text = re.sub(r"```thought\s*.*?\s*```", "", text, flags=re.DOTALL)
    return text.strip()

class ChatAgent:
    def __init__(self):
        # รวบรวม API Keys จากค่ายต่างๆ (หยิบจาก Environment ปลอดภัยไร้คีย์ดิบ)
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    async def get_response(self, prompt: str, history: list = None, status_callback=None, is_roblox: bool = False) -> dict:
        res = await self._get_response_core(prompt, history, status_callback, is_roblox)
        if res and isinstance(res, dict) and "reply" in res:
            res["reply"] = filter_thought_process(res["reply"])
        return res

    async def _get_response_core(self, prompt: str, history: list = None, status_callback=None, is_roblox: bool = False) -> dict:
        """ระบบสลับสมองข้ามค่ายอัตโนมัติพร้อมระบบ Tool Calling (Function Calling) และ Sliding Window History"""
        
        async def trigger_status(msg: str):
            if status_callback:
                try:
                    await status_callback(msg)
                except Exception:
                    pass

        await trigger_status("Thinking / Processing...")

        # Determine Environment Context
        from agent.tools import WORKSPACE_DIR
        import os

        # 1. Roblox Studio Check
        is_roblox_conn = is_roblox
        if not is_roblox_conn:
            prompt_lower = prompt.lower()
            if "roblox" in prompt_lower or "luau" in prompt_lower or "roblox studio" in prompt_lower:
                is_roblox_conn = True

        # 2. Cloned Repository Check
        has_repo = False
        if os.path.exists(WORKSPACE_DIR):
            if os.path.exists(os.path.join(WORKSPACE_DIR, ".git")):
                has_repo = True
            else:
                try:
                    items = [i for i in os.listdir(WORKSPACE_DIR) if i not in (".", "..", ".git", "__pycache__")]
                    if len(items) > 0:
                        has_repo = True
                except Exception:
                    pass

        # Build dynamic environment context segment for system prompt
        if is_roblox_conn:
            env_status = "ROBLOX STUDIO CONNECTION (Active Studio Session)"
            env_instruction = (
                "1. Recognize that you are interacting with Roblox Studio via HTTP/MCP Tunnel.\n"
                "2. Understand the Luau / Roblox engine context of the request.\n"
                "3. Utilize available Roblox MCP tools or structure your JSON response specifically so Roblox Studio scripts can execute the actions seamlessly."
            )
        elif has_repo:
            env_status = "WORKSPACE WITH CLONED REPOSITORY (Repository Present)"
            env_instruction = (
                "1. If the user requests to create or modify a file (e.g., \"create file html to create template UI\") WITHOUT explicitly providing a directory path, automatically default the file path to the Root Directory (`./`).\n"
                "2. Use workspace file tools (e.g., `write_file`) to write clean, production-ready code directly to disk.\n"
                "3. STRICTLY PROHIBITED: Do not write useless/trash code, boilerplate placeholder comments (e.g., // TODO), or unnecessary explanations inside the generated file."
            )
        else:
            env_status = "NO REPOSITORY (Empty Workspace / Standalone Chat)"
            env_instruction = (
                "1. Do NOT attempt to invoke disk writing tools or create files on the system (e.g., write_file, patch_file, execute_command to write files).\n"
                "2. Output the complete, fully functional code directly inside the chat as a clean Markdown code block so the user can easily review and copy it."
            )

        system_content = (
            "คุณคือ AI IDE Agent ที่มี Tools จัดการไฟล์และ Git\n\n"
            "==================================================\n"
            f"CURRENT DETECTED ENVIRONMENT CONTEXT:\n"
            f"- Environment Status: {env_status}\n"
            "==================================================\n"
            "[EXECUTION INSTRUCTION]\n"
            "Always analyze the current Environment Context (Has Repo, Is Roblox Studio) BEFORE deciding whether to execute disk tools, return code blocks in chat, or route commands through Roblox MCP.\n"
            "==================================================\n"
            "STRICT OPERATIONAL RULES FOR THIS ENVIRONMENT:\n"
            f"{env_instruction}\n"
            "==================================================\n\n"
            "ROBLOX DUAL-MODE SCRIPTING & CONTEXT RULES:\n"
            "คุณต้องสนับสนุนการเขียนสคริปต์ Roblox ทั้ง 2 รูปแบบแยกกันอย่างชัดเจนและไม่สับสน:\n"
            "- **Mode A (Repository / Rojo):** เขียนไฟล์ `.lua` หรือ `.luau` ลงในเครื่อง/โฟลเดอร์ Git Workspace ทันที (เช่น `src/Server/Script.lua` หรือ `ServerScript.lua`) ผ่านเครื่องมือเขียนไฟล์ (`write_file`, `patch_file`)\n"
            "  *เมื่อทำงานใน Mode A นี้ คุณต้องพิมพ์ข้อความยืนยันสถานะอย่างชัดเจนเสมอว่า*:\n"
            "  \"Created file `<ชื่อไฟล์>` in your Git Repository workspace. (Sync via Rojo or commit to GitHub to apply in Studio).\"\n"
            "- **Mode B (Live Roblox Studio via Plugin/Bridge):** หากมี Plugin/Bridge เชื่อมต่อสดกับ Roblox Studio จริงๆ เท่านั้น จึงจะส่งคำสั่งสร้าง/อัปเดตอ็อบเจกต์ (Instance) ใน `game.Workspace` ได้\n\n"
            "🚨 ข้อห้ามที่สำคัญที่สุด (STRICT NO-HALLUCINATION RULE):\n"
            "1. ห้ามสับสนระหว่าง `Repo Workspace` และ `Roblox Studio Explorer (game.Workspace)` เด็ดขาด!\n"
            "2. ห้ามเคลมหรือบอกว่าคุณได้สร้างอ็อบเจกต์ในโปรแกรม Roblox Studio จริงๆ เป็นอันขาด เว้นแต่ว่าจะมีการสั่งการผ่าน HTTP Bridge/Plugin ที่สำเร็จและได้รับการยืนยันจริงเท่านั้น!\n"
            "==================================================\n\n"
            "หากผู้ใช้สั่งให้ Clone Repo, อ่านไฟล์, หรือดูรายชื่อไฟล์ (และอยู่ในสถานะมี Repository) คุณต้องเรียกใช้ Tool "
            "(`git_clone`, `list_directory`, `read_file`, `patch_file`, `write_file`, `execute_command`) จริงๆ เท่านั้น "
            "**ห้ามเขียนคำอธิบายคำสั่ง Terminal หรือจำลองผลลัพธ์ขึ้นมาเองเด็ดขาด** "
            "คุณมีสิทธิ์เข้าถึง แก้ไข อ่าน และจัดการไฟล์ใน Workspace ผ่านเครื่องมือ (Tools) ที่มีให้ "
            "หลังรันเครื่องมือเสร็จสิ้น ให้สรุปคำตอบให้ผู้ใช้อย่างชัดเจนและเป็นมิตร"
        )

        system_message = {
            "role": "system",
            "content": system_content
        }

        # Build message history with role translation (user / assistant)
        formatted_history = []
        if history:
            for msg in history:
                role = "assistant" if msg.get("role") in ["ai", "assistant"] else "user"
                formatted_history.append({"role": role, "content": msg.get("content") or ""})
        else:
            formatted_history.append({"role": "user", "content": prompt})

        # Combine with system message
        messages = [system_message] + formatted_history

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
                                "description": "The relative path to the file inside the workspace. If no directory is specified, default to root directory './' (e.g., 'test.py')."
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
                                "description": "The relative path to the file inside the workspace. If no directory is specified, default to root directory './' (e.g., 'index.html')."
                            },
                            "content": {
                                "type": "string",
                                "description": "The complete text content to write into the file. MUST be clean, production-ready code. Boilerplate comment placeholders (e.g. // TODO) and explanation commentary inside the file are STRICTLY PROHIBITED."
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
                                "description": "The relative path to the file to patch. If no directory is specified, default to root directory './' (e.g., 'app.py')."
                            },
                            "search_block": {
                                "type": "string",
                                "description": "The exact block of code to search for."
                            },
                            "replace_block": {
                                "type": "string",
                                "description": "The block of code to replace it with. MUST be clean, production-ready code. Boilerplate comment placeholders (e.g. // TODO) are STRICTLY PROHIBITED."
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

        # Filter tools_schema based on repository state to strictly adhere to Rule 2 (No Repository -> No disk-writing/execution tools)
        if not has_repo:
            tools_schema = [
                t for t in tools_schema
                if t["function"]["name"] not in ["write_file", "patch_file", "execute_command"]
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

        def to_gemini_type(val):
            """Transforms standard JSON Schema types to Gemini REST uppercase conventions."""
            if isinstance(val, dict):
                new_dict = {}
                for k, v in val.items():
                    if k == "type" and isinstance(v, str):
                        new_dict[k] = v.upper()
                    else:
                        new_dict[k] = to_gemini_type(v)
                return new_dict
            elif isinstance(val, list):
                return [to_gemini_type(item) for item in val]
            return val

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
                            "temperature": 0.5,
                            "max_tokens": 2048
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

                            current_messages.append(message_resp)

                            tool_calls = message_resp.get("tool_calls")
                            if tool_calls:
                                for tool_call in tool_calls:
                                    tool_name = tool_call["function"]["name"]
                                    raw_args = tool_call["function"]["arguments"]

                                    if isinstance(raw_args, str):
                                        try:
                                            parsed_args = json.loads(raw_args)
                                        except Exception:
                                            parsed_args = {}
                                    else:
                                        parsed_args = raw_args or {}

                                    # Provide progress updates
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

                                    tool_output = execute_local_tool(tool_name, parsed_args)

                                    current_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call["id"],
                                        "name": tool_name,
                                        "content": json.dumps(tool_output, ensure_ascii=False)
                                    })
                                continue
                            else:
                                return {
                                    "reply": message_resp.get("content") or "",
                                    "model": "Groq (Llama-3.3-70b)",
                                    "total_tokens": total_tokens
                                }
                        else:
                            print(f"[Brain Switcher]: Groq failed with code {response.status_code}")
                            break
            except Exception as e:
                print(f"[Brain Switcher]: Groq เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 2: สลับไปใช้ Google Gemini อัตโนมัติ (พร้อมระบบ Tool Execution Loop) ---
        if self.gemini_key and "คีย์_" not in self.gemini_key:
            try:
                # Convert tools to Gemini REST format
                gemini_functions = []
                for tool in tools_schema:
                    func_def = tool["function"]
                    gemini_functions.append({
                        "name": func_def["name"],
                        "description": func_def["description"],
                        "parameters": to_gemini_type(func_def.get("parameters", {}))
                    })
                gemini_tools = [{"functionDeclarations": gemini_functions}]

                # Format sliding history contents
                gemini_contents = []
                if history:
                    for msg in history:
                        role = "model" if msg.get("role") in ["ai", "assistant"] else "user"
                        gemini_contents.append({
                            "role": role,
                            "parts": [{"text": msg.get("content") or ""}]
                        })
                else:
                    gemini_contents.append({
                        "role": "user",
                        "parts": [{"text": prompt}]
                    })

                max_turns = 10
                async with httpx.AsyncClient(timeout=30.0) as client:
                    for turn in range(max_turns):
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
                        payload = {
                            "systemInstruction": {
                                "parts": [{"text": system_message["content"]}]
                            },
                            "contents": gemini_contents,
                            "tools": gemini_tools,
                            "generationConfig": {
                                "maxOutputTokens": 2048
                            }
                        }

                        response = await client.post(
                            url,
                            headers={"Content-Type": "application/json"},
                            json=payload
                        )

                        if response.status_code == 200:
                            result = response.json()
                            candidate = result['candidates'][0]
                            content_resp = candidate['content']
                            parts = content_resp.get('parts', [])

                            # Append assistant turn to conversation context
                            gemini_contents.append(content_resp)

                            # Scan for tool calls
                            function_calls = [p.get("functionCall") for p in parts if p.get("functionCall")]

                            if function_calls:
                                for fc in function_calls:
                                    tool_name = fc["name"]
                                    args = fc.get("args", {})

                                    # Provide progress updates
                                    if tool_name == "read_file":
                                        await trigger_status(f"Reading file: {args.get('filepath', '')}...")
                                    elif tool_name == "write_file":
                                        await trigger_status(f"Updating code: {args.get('filepath', '')}...")
                                    elif tool_name == "patch_file":
                                        await trigger_status(f"Patching file: {args.get('filepath', '')}...")
                                    elif tool_name == "execute_command":
                                        await trigger_status(f"Running command: {args.get('command', '')}...")
                                    elif tool_name == "git_clone" or tool_name == "clone_repository":
                                        await trigger_status(f"Git cloning repository: {args.get('repo_url', '')}...")
                                    elif tool_name == "git_checkout":
                                        await trigger_status(f"Git checking out branch: {args.get('branch_name', '')}...")
                                    elif tool_name == "git_pull":
                                        await trigger_status("Git pulling updates...")
                                    elif tool_name == "git_status":
                                        await trigger_status("Checking git status...")
                                    else:
                                        await trigger_status(f"Running tool {tool_name}...")

                                    tool_output = execute_local_tool(tool_name, args)

                                    # Append tool result response
                                    gemini_contents.append({
                                        "role": "function",
                                        "parts": [{
                                            "functionResponse": {
                                                "name": tool_name,
                                                "response": {
                                                    "output": json.dumps(tool_output, ensure_ascii=False)
                                                }
                                            }
                                        }]
                                    })
                                continue
                            else:
                                reply_text = parts[0].get("text", "") if parts else ""
                                return {
                                    "reply": reply_text,
                                    "model": "Google Gemini 2.5 Flash",
                                    "total_tokens": 0
                                }
                        else:
                            print(f"[Brain Switcher]: Gemini failed with code {response.status_code}")
                            break
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
                            "temperature": 0.5,
                            "max_tokens": 2048
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

                            current_messages.append(message_resp)

                            tool_calls = message_resp.get("tool_calls")
                            if tool_calls:
                                for tool_call in tool_calls:
                                    tool_name = tool_call["function"]["name"]
                                    raw_args = tool_call["function"]["arguments"]

                                    if isinstance(raw_args, str):
                                        try:
                                            parsed_args = json.loads(raw_args)
                                        except Exception:
                                            parsed_args = {}
                                    else:
                                        parsed_args = raw_args or {}

                                    # Provide progress updates
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

                                    tool_output = execute_local_tool(tool_name, parsed_args)

                                    current_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call["id"],
                                        "name": tool_name,
                                        "content": json.dumps(tool_output, ensure_ascii=False)
                                    })
                                continue
                            else:
                                return {
                                    "reply": message_resp.get("content") or "",
                                    "model": "OpenAI (GPT-4o-Mini)",
                                    "total_tokens": total_tokens
                                }
                        else:
                            print(f"[Brain Switcher]: OpenAI failed with code {response.status_code}")
                            break
            except Exception as e:
                print(f"[Brain Switcher]: OpenAI เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 4: ด่านสุดท้ายสลับไปใช้ OpenRouter (Auto-Free Models / openrouter/free) (พร้อมระบบ Tool Execution Loop) ---
        if self.openrouter_key and "คีย์_" not in self.openrouter_key:
            try:
                max_turns = 10
                current_messages = list(messages)
                total_tokens = 0

                async with httpx.AsyncClient(timeout=30.0) as client:
                    for turn in range(max_turns):
                        payload = {
                            "model": "openrouter/free",
                            "messages": current_messages,
                            "tools": tools_schema,
                            "tool_choice": "auto",
                            "temperature": 0.5,
                            "max_tokens": 2048
                        }

                        response = await client.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {self.openrouter_key}",
                                "Content-Type": "application/json"
                            },
                            json=payload
                        )

                        if response.status_code == 200:
                            result = response.json()
                            total_tokens += result.get("usage", {}).get("total_tokens", 0)
                            message_resp = result["choices"][0]["message"]

                            current_messages.append(message_resp)

                            tool_calls = message_resp.get("tool_calls")
                            if tool_calls:
                                for tool_call in tool_calls:
                                    tool_name = tool_call["function"]["name"]
                                    raw_args = tool_call["function"]["arguments"]

                                    if isinstance(raw_args, str):
                                        try:
                                            parsed_args = json.loads(raw_args)
                                        except Exception:
                                            parsed_args = {}
                                    else:
                                        parsed_args = raw_args or {}

                                    # Provide progress updates
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

                                    tool_output = execute_local_tool(tool_name, parsed_args)

                                    current_messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call["id"],
                                        "name": tool_name,
                                        "content": json.dumps(tool_output, ensure_ascii=False)
                                    })
                                continue
                            else:
                                return {
                                    "reply": message_resp.get("content") or "",
                                    "model": "OpenRouter (Free)",
                                    "total_tokens": total_tokens
                                }
                        else:
                            print(f"[Brain Switcher]: OpenRouter failed with code {response.status_code}")
                            break
            except Exception as e:
                print(f"[Brain Switcher]: OpenRouter เชื่อมต่อไม่ได้ -> {e}")

        # --- กรณีสุดท้าย: ถ้าคีย์ทั้งหมดในเครื่องไม่มี หรือล่มพร้อมกันหมด ---
        return {
            "reply": "⚠️ [ระบบขัดข้อง]: ตอนนี้ค่าย AI ทั้งหมด (Groq, Gemini, OpenAI, OpenRouter) ติดลิมิตโควตาฟรีพร้อมกันหรือคีย์ขัดข้องครับสหาย โปรดรอให้ระบบรีเซ็ตสักครู่เด็ดขาดด้วยนะครับ!",
            "model": "All Providers Exhausted",
            "total_tokens": 0
        }
