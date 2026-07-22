import os
import json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_config.json")

def load_mcp_config() -> dict:
    """Reads and parses the mcp_config.json from the project root."""
    if not os.path.exists(CONFIG_PATH):
        # Create base config if not present
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"mcpServers": {}}, f, indent=2)

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[MCP Loader Error]: Failed to read/parse config: {e}")
        return {"mcpServers": {}}

def validate_mcp_config(raw_json_str: str) -> dict:
    """Validates the structure of an incoming MCP config JSON string."""
    try:
        data = json.loads(raw_json_str)
    except json.JSONDecodeError as jde:
        return {"status": "error", "message": f"Invalid JSON Syntax: {str(jde)}"}

    if not isinstance(data, dict):
        return {"status": "error", "message": "Root elements of config must be a JSON Object."}

    if "mcpServers" not in data:
        return {"status": "error", "message": "Config must contain an 'mcpServers' object key."}

    mcp_servers = data.get("mcpServers")
    if not isinstance(mcp_servers, dict):
        return {"status": "error", "message": "'mcpServers' key must be a JSON Object."}

    # Validate each server structure
    for name, server in mcp_servers.items():
        if not isinstance(server, dict):
            return {"status": "error", "message": f"Server '{name}' definition must be a JSON Object."}

    return {"status": "success", "data": data}
