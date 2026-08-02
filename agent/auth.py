import os
import datetime
from typing import Optional
import jwt
from fastapi import Request, HTTPException
from database import db_helper

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-jwt-key-999")
JWT_ALGORITHM = "HS256"

# API Token for Roblox Studio & system integrations
API_SECRET_TOKEN = os.environ.get("API_SECRET_TOKEN", "super-secret-ide-agent-token-123")

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Creates a custom signed JSON Web Token (JWT)."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request) -> Optional[dict]:
    """
    Decodes and validates a JWT token from the Authorization header or secure cookies.
    """
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # Fallback to cookie check if header is missing
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated: No active token or session.")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        github_id = payload.get("sub")
        if not github_id:
            raise HTTPException(status_code=401, detail="Invalid token payload: Missing user identity.")

        user = await db_helper.get_user(github_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found in system storage.")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired: Token has expired.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid session: Token is malformed.")

async def get_current_user_or_api_client(request: Request) -> Optional[dict]:
    """
    Decodes and validates either:
    1. A JWT from Authorization header / cookies
    2. An API token from X-API-Token header
    This provides flexible policy for Roblox Studio & API Clients.
    """
    # 1. Check API token first (e.g. Roblox Studio integration)
    api_token = request.headers.get("X-API-Token")
    if api_token and api_token == API_SECRET_TOKEN:
        return {"username": "Roblox_Studio_Client", "is_api_client": True}

    # 2. Check JWT Auth
    try:
        user = await get_current_user(request)
        return user
    except HTTPException:
        # If no auth header/cookie was present, let's return None (optional public access)
        auth_header = request.headers.get("Authorization")
        api_token = request.headers.get("X-API-Token")
        cookie_token = request.cookies.get("access_token")
        if not auth_header and not api_token and not cookie_token:
            return None
        raise
