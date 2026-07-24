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
        # รวบรวม API Keys จากค่ายต่างๆ (หยิบจาก Environment ปลอดภัยไร้คีย์ดิบ)
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    async def get_response(self, prompt: str, history: list = None, status_callback=None, request_context: dict = None) -> dict:
        """ระบบสลับสมองข้ามค่ายอัตโนมัติพร้อมระบบ Tool Calling (Function Calling) และ Sliding Window History"""
        
        # Load keys dynamically from environment on every request to pick up runtime updates
        from dotenv import load_dotenv
        load_dotenv()
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

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
                "คุณคือ AI IDE Agent ที่มี Tools จัดการไฟล์และ Git "
                "หากผู้ใช้สั่งให้ Clone Repo, อ่านไฟล์, หรือดูรายชื่อไฟล์ คุณต้องเรียกใช้ Tool "
                "(`git_clone`, `list_directory`, `read_file`, `patch_file`, `write_file`, `execute_command`) จริงๆ เท่านั้น "
                "**ห้ามเขียนคำอธิบายคำสั่ง Terminal หรือจำลองผลลัพธ์ขึ้นมาเองเด็ดขาด** "
                "คุณมีสิทธิ์เข้าถึง แก้ไข อ่าน และจัดการไฟล์ใน Workspace ผ่านเครื่องมือ (Tools) ที่มีให้ "
                "หลังรันเครื่องมือเสร็จสิ้น ให้สรุปคำตอบให้ผู้ใช้อย่างชัดเจนและเป็นมิตร"
            )
        }

        # Determine environment state and apply rules
        from agent.tools import WORKSPACE_DIR
        has_repo = False
        if os.path.exists(WORKSPACE_DIR):
            try:
                items = [i for i in os.listdir(WORKSPACE_DIR) if i not in [".pytest_cache", "__pycache__", ".git"]]
                if len(items) > 0:
                    has_repo = True
                elif os.path.exists(os.path.join(WORKSPACE_DIR, ".git")):
                    has_repo = True
            except Exception:
                has_repo = False

        is_roblox_studio = False
        if request_context:
            is_roblox_studio = request_context.get("is_roblox_studio", False)
            if not is_roblox_studio:
                headers = request_context.get("headers", {})
                for k, v in headers.items():
                    if "roblox" in k.lower() or "roblox" in str(v).lower():
                        is_roblox_studio = True
                        break
        # also detect Roblox Studio via prompt/payload context
        if not is_roblox_studio and prompt:
            if "roblox" in prompt.lower() or "luau" in prompt.lower() or "studio session" in prompt.lower():
                is_roblox_studio = True

        additional_rules = ""
        if has_repo:
            additional_rules += (
                "\n\n[RULE 1: WORKSPACE WITH CLONED REPOSITORY (Repository Present)]\n"
                "- หากผู้ใช้สั่งให้สร้างหรือแก้ไขไฟล์ (เช่น 'สร้างไฟล์ html') โดยไม่ได้ระบุเส้นทางโฟลเดอร์ (directory path) อย่างชัดเจน ให้กำหนดเส้นทางไฟล์เริ่มต้นไปที่ไดเรกทอรีราก (Root Directory: `./`) โดยอัตโนมัติ\n"
                "- ใช้เครื่องมือจัดการไฟล์ใน workspace (เช่น `write_file`, `patch_file`) เพื่อเขียนโค้ดที่พร้อมใช้งานจริง (production-ready) ลงดิสก์โดยตรง\n"
                "- ข้อห้ามเด็ดขาด (STRICTLY PROHIBITED): ห้ามเขียนโค้ดที่ใช้งานไม่ได้/ขยะ, ห้ามใส่คอมเมนต์หลอกลวงหรือ boilerplate placeholder (เช่น // TODO), และห้ามอธิบายความไร้ประโยชน์/อธิบายฟุ่มเฟือยภายในไฟล์ที่สร้างขึ้นเป็นอันขาด"
            )
        else:
            additional_rules += (
                "\n\n[RULE 2: NO REPOSITORY (Empty Workspace / Standalone Chat)]\n"
                "- ขณะนี้ไม่มี repository ใดที่โคลนไว้ และ workspace ว่างเปล่า\n"
                "- ห้ามพยายามเรียกใช้เครื่องมือเขียนลงดิสก์หรือสร้างไฟล์บนระบบเด็ดขาด (เครื่องมือเขียนไฟล์เช่น write_file และ patch_file ถูกปิดใช้งานในโหมดนี้)\n"
                "- ให้สร้างและแสดงโค้ดฉบับเต็มที่ทำงานได้สมบูรณ์และพร้อมใช้งานจริงส่งกลับมาในแชทโดยตรงในรูปแบบ Markdown code block เพื่อให้ผู้ใช้สามารถตรวจสอบและคัดลอกได้อย่างง่ายดาย"
            )

        if is_roblox_studio:
            # a. Intent Classification
            prompt_lower = prompt.lower()
            intent = "UNKNOWN"
            if any(x in prompt_lower for x in ["create", "add", "make", "insert", "new"]):
                intent = "CREATE"
            elif any(x in prompt_lower for x in ["read", "inspect", "get", "view", "show", "list", "tree", "children"]):
                intent = "READ/INSPECT"
            elif any(x in prompt_lower for x in ["update", "patch", "modify", "change", "set", "write"]):
                intent = "UPDATE/PATCH"
            elif any(x in prompt_lower for x in ["delete", "remove", "destroy", "clear"]):
                intent = "DELETE"

            # b. Hierarchy Inspection (Safety Check)
            safety_checks_guidance = ""
            if intent in ["UPDATE/PATCH", "DELETE"]:
                safety_checks_guidance = (
                    "\n[SAFETY WARNING: HIERARCHY INSPECTION REQUIRED]\n"
                    "- คุณกำลังจะทำการแก้ไขหรือลบ instance เดิมใน Roblox Studio "
                    "โปรดตรวจสอบโครงสร้างโฟลเดอร์หรือตำแหน่งเป้าหมายด้วยเครื่องมือ `roblox_get_children` หรือ `roblox_get_instance_tree` "
                    "ก่อนเริ่มการดำเนินการลบหรือแก้ไข เพื่อความปลอดภัยและป้องกันข้อผิดพลาด"
                )

            # c. Target Path Resolver
            from agent.mcp_registry import ROBLOX_SERVICE_RESOLVER
            matched_services = []
            for kw, service in ROBLOX_SERVICE_RESOLVER.items():
                if kw in prompt_lower:
                    matched_services.append(f"'{kw}' -> '{service}'")
            resolved_service_guidance = ""
            if matched_services:
                resolved_service_guidance = (
                    "\n[TARGET PATH RESOLVED SERVICES]\n"
                    "ระบบตรวจพบคำระบุบริการเป้าหมายของ Roblox และแนะนำแปลงเส้นทางอัตโนมัติ:\n" +
                    "\n".join(f"- {s}" for s in matched_services) + "\n"
                    "โปรดระบุ parentPath เป็นบริการเหล่านี้ตามที่ได้รับการสกัดความต้องการ"
                )

            intent_summary = (
                f"\n\n[PRE-EXECUTION REASONING (Chain-of-Thought)]\n"
                f"- Classified Intent: {intent}\n"
                f"{resolved_service_guidance}"
                f"{safety_checks_guidance}"
            )

            additional_rules += (
                "\n\n[RULE 3: ROBLOX STUDIO CONNECTION (Active Studio Session)]\n"
                "- ตรวจพบว่าคำขอนี้มาจาก Roblox Studio ผ่านทาง HTTP/MCP Tunnel หรือเกี่ยวข้องกับ Roblox\n"
                "- ให้ตระหนักว่าคุณกำลังสื่อสารและตอบโต้กับ Roblox Studio\n"
                "- ทำความเข้าใจและรันงานภายใต้บริบทของ Luau / Roblox engine\n"
                "- เรียกใช้งานเครื่องมือ Roblox MCP ที่มี หรือปรับแต่งโครงสร้างการตอบกลับรูปแบบ JSON ของคุณเพื่อให้สคริปต์ของ Roblox Studio สามารถประมวลผลและนำไปรันได้อย่างราบรื่นและมีประสิทธิภาพ\n"
                "- หลักการเขียนโค้ด Luau ที่สะอาดที่สุด (STRICTLY ENFORCE CLEANEST-CODE): ห้ามใส่โค้ดคอมเมนต์ boilerplate ที่ไร้ประโยชน์ หรือโค้ดขยะเป็นอันขาด ทุกบรรทัดต้องพร้อมใช้งานได้จริง\n"
                "- การจัดลำดับคำสั่งเรียกใช้เครื่องมือ MCP (SEQUENCING TOOL CALLS): ให้ทำลำดับการสร้างและตั้งค่า instance ต่างๆ เป็นระบบ pipeline ต่อเนื่องในการสนทนาตาเดียวอย่างรวดเร็ว (เช่น สร้าง ScreenGui -> สร้าง Frame -> สร้าง TextButton ในการรันทีเดียว)"
                f"{intent_summary}"
            )

        system_message["content"] += additional_rules

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
        async def execute_local_tool(name: str, args: dict) -> dict:
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
                elif name.startswith("roblox_"):
                    from agent.mcp_registry import execute_roblox_mcp_tool
                    await trigger_status(f"Executing Roblox Tool: {name} with args: {args}...")
                    result = await execute_roblox_mcp_tool(name, args)
                    # feedback loop: check for error and retry with self-correction
                    if result.get("status") == "error":
                        error_msg = result.get("message", "")
                        await trigger_status(f"Roblox Tool failed: {error_msg}. Attempting self-correction retry...")
                        corrected = False
                        # Strategy 1: Path doesn't start with game. but is specified (e.g. "Workspace.Part" -> "game.Workspace.Part")
                        for path_key in ["parentPath", "instancePath", "scriptPath", "rootPath"]:
                            if path_key in args and isinstance(args[path_key], str):
                                val = args[path_key]
                                if val and not val.startswith("game.") and not val.startswith("game"):
                                    args[path_key] = f"game.{val}"
                                    corrected = True
                        # Strategy 2: If parentPath is completely missing or empty, resolve it
                        if "parentPath" in args and not args["parentPath"]:
                            args["parentPath"] = "game.Workspace"
                            corrected = True
                        if corrected:
                            await trigger_status(f"Retrying corrected Roblox Tool: {name} with args: {args}...")
                            result = await execute_roblox_mcp_tool(name, args)
                        else:
                            result["message"] = (
                                f"[ANALYSIS OF FAIL]: Roblox Studio returned: {error_msg}. "
                                "Suggestion: Check if parentPath exists or verify target path spelling."
                            )
                    return result
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

        # Filter active tools based on environment rules
        active_tools = list(tools_schema)
        if not has_repo:
            active_tools = [t for t in active_tools if t["function"]["name"] not in ["write_file", "patch_file"]]

        # Dynamic MCP tools integration if Roblox Studio session is active
        if is_roblox_studio:
            from agent.mcp_registry import get_mcp_tools_schemas
            active_tools.extend(get_mcp_tools_schemas())

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
                            "tools": active_tools,
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

                                    tool_output = await execute_local_tool(tool_name, parsed_args)

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
                            print(f"[Brain Switcher]: Groq failed with code {response.status_code}. Response: {response.text}")
                            break
            except Exception as e:
                print(f"[Brain Switcher]: Groq เชื่อมต่อไม่ได้ -> {e}")

        # --- ลำดับที่ 2: สลับไปใช้ Google Gemini อัตโนมัติ (พร้อมระบบ Tool Execution Loop) ---
        if self.gemini_key and "คีย์_" not in self.gemini_key:
            try:
                # Convert tools to Gemini REST format
                gemini_functions = []
                for tool in active_tools:
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

                                    tool_output = await execute_local_tool(tool_name, args)

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
                            print(f"[Brain Switcher]: Gemini failed with code {response.status_code}. Response: {response.text}")
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
                            "tools": active_tools,
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

                                    tool_output = await execute_local_tool(tool_name, parsed_args)

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
                            print(f"[Brain Switcher]: OpenAI failed with code {response.status_code}. Response: {response.text}")
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
                            "tools": active_tools,
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

                                    tool_output = await execute_local_tool(tool_name, parsed_args)

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
                            print(f"[Brain Switcher]: OpenRouter failed with code {response.status_code}. Response: {response.text}")
                            break
            except Exception as e:
                print(f"[Brain Switcher]: OpenRouter เชื่อมต่อไม่ได้ -> {e}")

        # --- กรณีสุดท้าย: ถ้าคีย์ทั้งหมดในเครื่องไม่มี หรือล่มพร้อมกันหมด ---
        return {
            "reply": "⚠️ [ระบบขัดข้อง]: ตอนนี้ค่าย AI ทั้งหมด (Groq, Gemini, OpenAI, OpenRouter) ติดลิมิตโควตาฟรีพร้อมกันหรือคีย์ขัดข้องครับสหาย โปรดรอให้ระบบรีเซ็ตสักครู่เด็ดขาดด้วยนะครับ!",
            "model": "All Providers Exhausted",
            "total_tokens": 0
        }
