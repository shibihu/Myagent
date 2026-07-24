import os
import json
import httpx
from agent.mcp_loader import load_mcp_config

# Dynamic Roblox Studio MCP Tools Registry
ROBLOX_MCP_TOOLS = {
    "create_instance": {
        "description": "Creates a new instance of a specific class in the specified Roblox hierarchy.",
        "parameters": {
            "type": "object",
            "properties": {
                "className": {"type": "string", "description": "The class name of the instance (e.g., Part, Script, ScreenGui, Frame)."},
                "parentPath": {"type": "string", "description": "The absolute path in the hierarchy (e.g., game.Workspace or Workspace, StarterGui). Defaults to game.Workspace."},
                "properties": {"type": "object", "description": "Key-value map of properties to apply to the newly created instance."}
            },
            "required": ["className"]
        }
    },
    "get_children": {
        "description": "Lists all children of a specific instance in Roblox Studio.",
        "parameters": {
            "type": "object",
            "properties": {
                "parentPath": {"type": "string", "description": "The target instance hierarchy path (e.g., game.Workspace)."}
            },
            "required": ["parentPath"]
        }
    },
    "get_instance_tree": {
        "description": "Recursively retrieves the children and descendants of a root path.",
        "parameters": {
            "type": "object",
            "properties": {
                "rootPath": {"type": "string", "description": "The root path of the tree (defaults to game.Workspace)."},
                "depth": {"type": "integer", "description": "Maximum recursive traversal depth.", "default": 3}
            }
        }
    },
    "delete_instance": {
        "description": "Deletes a specific instance from the Roblox project hierarchy.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The absolute path of the instance to delete."}
            },
            "required": ["instancePath"]
        }
    },
    "get_properties": {
        "description": "Retrieves the full list of properties and values for a specific Roblox instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The target instance path."}
            },
            "required": ["instancePath"]
        }
    },
    "set_properties": {
        "description": "Updates multiple property values for a specific instance in Roblox Studio.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The target instance path."},
                "properties": {"type": "object", "description": "Key-value pair dictionary of properties to update."}
            },
            "required": ["instancePath", "properties"]
        }
    },
    "update_script_source": {
        "description": "Replaces the entire source code of a Script, LocalScript, or ModuleScript.",
        "parameters": {
            "type": "object",
            "properties": {
                "scriptPath": {"type": "string", "description": "The absolute path to the target script instance."},
                "source": {"type": "string", "description": "The complete, optimized Luau source code."}
            },
            "required": ["scriptPath", "source"]
        }
    },
    "get_script_source": {
        "description": "Reads and returns the complete text source of a script instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "scriptPath": {"type": "string", "description": "The path to the target script."}
            },
            "required": ["scriptPath"]
        }
    },
    "run_command": {
        "description": "Executes a command script or Luau code snippet in the Roblox Studio Command Bar.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The Luau script code snippet to execute."}
            },
            "required": ["command"]
        }
    },
    "get_services": {
        "description": "Lists all active core services within the Roblox game object context.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "find_first_child": {
        "description": "Checks for the existence of a child by name on a specific parent instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "parentPath": {"type": "string", "description": "The parent instance path."},
                "childName": {"type": "string", "description": "The exact name of the child to search for."}
            },
            "required": ["parentPath", "childName"]
        }
    },
    "find_first_descendant": {
        "description": "Recursively searches for a descendant by name under a parent path.",
        "parameters": {
            "type": "object",
            "properties": {
                "parentPath": {"type": "string", "description": "The parent instance path."},
                "descendantName": {"type": "string", "description": "The name of the descendant."}
            },
            "required": ["parentPath", "descendantName"]
        }
    },
    "get_attribute": {
        "description": "Retrieves the value of a specific attribute on a Roblox instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The target instance path."},
                "attributeName": {"type": "string", "description": "The attribute name."}
            },
            "required": ["instancePath", "attributeName"]
        }
    },
    "set_attribute": {
        "description": "Sets the value of a specific attribute on a Roblox instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The target instance path."},
                "attributeName": {"type": "string", "description": "The attribute name."},
                "value": {"type": "string", "description": "The attribute value to assign."}
            },
            "required": ["instancePath", "attributeName", "value"]
        }
    },
    "get_attributes": {
        "description": "Gets all attributes associated with a specific Roblox instance.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The target instance path."}
            },
            "required": ["instancePath"]
        }
    },
    "play_solo": {
        "description": "Starts an active Play Solo testing session inside Roblox Studio.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "stop_play_solo": {
        "description": "Stops the active Play Solo testing session in Roblox Studio.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "insert_model": {
        "description": "Inserts a free model or published asset ID into the active project hierarchy.",
        "parameters": {
            "type": "object",
            "properties": {
                "assetId": {"type": "string", "description": "The Roblox Asset ID to insert."},
                "parentPath": {"type": "string", "description": "Where in the hierarchy to insert the model."}
            },
            "required": ["assetId"]
        }
    },
    "export_model": {
        "description": "Saves/Exports a specific instance to a local file path as an rbxmx or rbxm model file.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The instance to export."},
                "filePath": {"type": "string", "description": "The target local filepath on disk."}
            },
            "required": ["instancePath", "filePath"]
        }
    },
    "get_selection": {
        "description": "Retrieves the paths of currently selected instances in the Roblox Studio Explorer.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "set_selection": {
        "description": "Updates active explorer selection in Roblox Studio.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePaths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of paths to select."
                }
            },
            "required": ["instancePaths"]
        }
    },
    "open_script": {
        "description": "Opens a script inside the Roblox Studio code editor panel.",
        "parameters": {
            "type": "object",
            "properties": {
                "scriptPath": {"type": "string", "description": "The path to the target script."}
            },
            "required": ["scriptPath"]
        }
    },
    "close_script": {
        "description": "Closes an open script in Roblox Studio editor panels.",
        "parameters": {
            "type": "object",
            "properties": {
                "scriptPath": {"type": "string", "description": "The path to the target script."}
            },
            "required": ["scriptPath"]
        }
    },
    "get_open_scripts": {
        "description": "Retrieves paths of all currently open script editor tabs.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "clear_all_children": {
        "description": "Deletes all descendants and child instances under a specific path.",
        "parameters": {
            "type": "object",
            "properties": {
                "parentPath": {"type": "string", "description": "The parent target path."}
            },
            "required": ["parentPath"]
        }
    },
    "clone_instance": {
        "description": "Duplicates an instance and parents it appropriately.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The target path of the instance to clone."},
                "parentPath": {"type": "string", "description": "Where to place the clone."}
            },
            "required": ["instancePath"]
        }
    },
    "move_instance": {
        "description": "Changes the parent of a target instance in Roblox hierarchy.",
        "parameters": {
            "type": "object",
            "properties": {
                "instancePath": {"type": "string", "description": "The target instance path."},
                "parentPath": {"type": "string", "description": "The path of the new parent."}
            },
            "required": ["instancePath", "parentPath"]
        }
    }
}

# Target Path Resolver logic
# Mapping commonly omitted paths to actual Roblox service roots
ROBLOX_SERVICE_RESOLVER = {
    "leaderstats": "game.ServerScriptService",
    "leaderstat": "game.ServerScriptService",
    "ui": "game.StarterGui",
    "screenui": "game.StarterGui",
    "gui": "game.StarterGui",
    "module": "game.ReplicatedStorage",
    "modulescript": "game.ReplicatedStorage",
    "remoteevent": "game.ReplicatedStorage",
    "remotefunction": "game.ReplicatedStorage"
}

def resolve_target_path(omitted_path_keyword: str) -> str:
    """
    Resolves Roblox service parent routes if the user omits explicit paths.
    E.g. 'leaderstats' -> 'game.ServerScriptService'
    """
    kw_clean = omitted_path_keyword.lower().strip()
    return ROBLOX_SERVICE_RESOLVER.get(kw_clean, "game.Workspace")

def get_mcp_tools_schemas() -> list:
    """
    Transforms the registered 27 tools to OpenAI-compatible tool definitions.
    """
    schemas = []
    for name, definition in ROBLOX_MCP_TOOLS.items():
        schemas.append({
            "type": "function",
            "function": {
                "name": f"roblox_{name}",
                "description": definition["description"],
                "parameters": definition["parameters"]
            }
        })
    return schemas

async def execute_roblox_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """
    Executes tool requests by calling the configured Roblox Studio HTTP/MCP Tunnel.
    Implements standard HTTP-REST tunnel routes and JSON-RPC fallback.
    """
    config = load_mcp_config()
    server_info = config.get("mcpServers", {}).get("roblox-studio", {})
    url = server_info.get("url") or "http://localhost:3000"

    # Strip "roblox_" prefix if present in the caller tool_name
    real_name = tool_name
    if tool_name.startswith("roblox_"):
        real_name = tool_name[7:]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Attempt REST invocation: POST /tools/<tool_name>
            try:
                response = await client.post(f"{url}/tools/{real_name}", json=arguments)
                if response.status_code == 200:
                    return {"status": "success", "result": response.json()}
            except Exception:
                pass

            # 2. JSON-RPC fallback invocation: POST /
            rpc_payload = {
                "jsonrpc": "2.0",
                "method": f"tools/{real_name}",
                "params": arguments,
                "id": 1
            }
            response_rpc = await client.post(url, json=rpc_payload)
            if response_rpc.status_code == 200:
                rpc_data = response_rpc.json()
                if "error" in rpc_data:
                    return {"status": "error", "message": rpc_data["error"].get("message", "Unknown RPC error")}
                return {"status": "success", "result": rpc_data.get("result", rpc_data)}

            return {"status": "error", "message": f"Roblox Studio responded with status code {response_rpc.status_code}"}
    except Exception as e:
        # If Roblox Studio is completely disconnected, return simulated fallback behavior or clear error
        return {
            "status": "error",
            "message": f"Roblox Studio connection failed. Please ensure Roblox Studio is open and MCP server is running at {url}. Error: {str(e)}"
        }
