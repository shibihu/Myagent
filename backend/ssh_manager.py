import os
import json
import uuid
from typing import Dict, List, Optional
from cryptography.fernet import Fernet

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_FILE = os.path.join(BASE_DIR, ".encryption_key")
SERVERS_FILE = os.path.join(BASE_DIR, "ssh_servers.json")

# Initialize / Load encryption key
if os.path.exists(KEY_FILE):
    try:
        with open(KEY_FILE, "rb") as f:
            ENCRYPTION_KEY = f.read().strip()
            # Validate key format
            Fernet(ENCRYPTION_KEY)
    except Exception:
        ENCRYPTION_KEY = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(ENCRYPTION_KEY)
else:
    ENCRYPTION_KEY = Fernet.generate_key()
    with open(KEY_FILE, "wb") as f:
        f.write(ENCRYPTION_KEY)

cipher_suite = Fernet(ENCRYPTION_KEY)

def encrypt_value(val: Optional[str]) -> Optional[str]:
    """Encrypts a plaintext string to an encrypted token."""
    if not val:
        return None
    return cipher_suite.encrypt(val.encode("utf-8")).decode("utf-8")

def decrypt_value(token: Optional[str]) -> Optional[str]:
    """Decrypts an encrypted token back to plaintext."""
    if not token:
        return None
    try:
        return cipher_suite.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return None

def load_ssh_servers() -> Dict[str, dict]:
    """Loads all saved SSH servers from the JSON file."""
    if os.path.exists(SERVERS_FILE):
        try:
            with open(SERVERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_ssh_servers(servers: Dict[str, dict]) -> None:
    """Atomically saves SSH servers to the JSON file."""
    temp_path = SERVERS_FILE + ".tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(servers, f, indent=4, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, SERVERS_FILE)
    except Exception as e:
        print(f"[SSH Manager] Error saving to {SERVERS_FILE}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

import re

def validate_host(host: str) -> None:
    """
    Validates a hostname or IP address. Throws ValueError if invalid.
    """
    if not host:
        raise ValueError("Host address cannot be empty.")

    trimmed = host.strip()

    # Exclude protocol prefixes (should have been stripped by frontend, but prevent backend entry)
    if re.match(r'^[a-zA-Z0-9+.-]+://', trimmed):
        raise ValueError("Host address must not contain a protocol prefix (e.g. 'tcp://' or 'ssh://').")

    # Exclude ports (should have been separated)
    if ":" in trimmed:
        raise ValueError("Host address must not contain a port suffix (e.g. ':33183'). Enter the port separately.")

    # Check for trailing dots or empty labels
    if trimmed.endswith(".") or ".." in trimmed:
        raise ValueError("Host address has an invalid format (trailing dot or consecutive dots).")

    # Standard Hostname / IP address validation
    # Allowed: letters, numbers, hyphens, dots
    hostname_regex = re.compile(
        r'^('
        r'(localhost)|' # localhost
        r'(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])' # domains
        r')$'
    )

    ipv4_regex = re.compile(
        r'^((25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)$'
    )

    ipv6_regex = re.compile(r'^([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}$|^([0-9a-fA-F]{1,4}:){1,7}:$|^([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$')

    if not (hostname_regex.match(trimmed) or ipv4_regex.match(trimmed) or ipv6_regex.match(trimmed) or trimmed == "localhost"):
        raise ValueError("Host address format is invalid. Must be a valid IP address or domain hostname (e.g. '192.168.1.1' or 'ssh.site.com').")

def get_masked_server(server_id: str, server_data: dict) -> dict:
    """Returns a server profile with sensitive credential fields redacted/masked."""
    return {
        "id": server_id,
        "nickname": server_data.get("nickname", ""),
        "host": server_data.get("host", ""),
        "port": server_data.get("port", 22),
        "username": server_data.get("username", ""),
        "auth_method": server_data.get("auth_method", "password"),
        "has_password": bool(server_data.get("password")),
        "has_private_key": bool(server_data.get("private_key")),
        "has_passphrase": bool(server_data.get("passphrase")),
    }

def create_ssh_server(data: dict) -> dict:
    """Creates a new SSH server configuration, encrypting credentials."""
    validate_host(data.get("host", ""))
    servers = load_ssh_servers()
    server_id = str(uuid.uuid4())

    server_record = {
        "nickname": data.get("nickname", ""),
        "host": data.get("host", "").strip(),
        "port": int(data.get("port", 22)),
        "username": data.get("username", ""),
        "auth_method": data.get("auth_method", "password"),
        "password": encrypt_value(data.get("password")),
        "private_key": encrypt_value(data.get("private_key")),
        "passphrase": encrypt_value(data.get("passphrase"))
    }

    servers[server_id] = server_record
    save_ssh_servers(servers)
    return get_masked_server(server_id, server_record)

def list_ssh_servers() -> List[dict]:
    """Lists all SSH server configurations (masked)."""
    servers = load_ssh_servers()
    return [get_masked_server(sid, data) for sid, data in servers.items()]

def get_ssh_server_decrypted(server_id: str) -> Optional[dict]:
    """Retrieves a fully decrypted SSH server configuration for backend SSH client use."""
    servers = load_ssh_servers()
    if server_id not in servers:
        return None
    data = servers[server_id]
    return {
        "id": server_id,
        "nickname": data.get("nickname", ""),
        "host": data.get("host", ""),
        "port": int(data.get("port", 22)),
        "username": data.get("username", ""),
        "auth_method": data.get("auth_method", "password"),
        "password": decrypt_value(data.get("password")),
        "private_key": decrypt_value(data.get("private_key")),
        "passphrase": decrypt_value(data.get("passphrase"))
    }

def update_ssh_server(server_id: str, data: dict) -> Optional[dict]:
    """Updates an existing SSH server, encrypting any updated credential fields."""
    if "host" in data:
        validate_host(data["host"])

    servers = load_ssh_servers()
    if server_id not in servers:
        return None

    existing = servers[server_id]
    existing["nickname"] = data.get("nickname", existing["nickname"])
    existing["host"] = data.get("host", existing["host"]).strip()
    existing["port"] = int(data.get("port", existing["port"]))
    existing["username"] = data.get("username", existing["username"])
    existing["auth_method"] = data.get("auth_method", existing["auth_method"])

    # Only overwrite credentials if specifically passed (i.e. not masked/empty)
    if "password" in data and data["password"] is not None:
        existing["password"] = encrypt_value(data["password"])
    if "private_key" in data and data["private_key"] is not None:
        existing["private_key"] = encrypt_value(data["private_key"])
    if "passphrase" in data and data["passphrase"] is not None:
        existing["passphrase"] = encrypt_value(data["passphrase"])

    servers[server_id] = existing
    save_ssh_servers(servers)
    return get_masked_server(server_id, existing)

def delete_ssh_server(server_id: str) -> bool:
    """Deletes an SSH server configuration."""
    servers = load_ssh_servers()
    if server_id in servers:
        del servers[server_id]
        save_ssh_servers(servers)
        return True
    return False
