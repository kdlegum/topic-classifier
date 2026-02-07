import os
import requests
from jose import jwt, JWTError
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()

SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID", "aefhkwhqvlcbvdpoyokn")
SUPABASE_JWKS_URL = f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1/.well-known/jwks.json"
SUPABASE_ISSUER = f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1"

# fetch JWKS once at startup
jwks = requests.get(SUPABASE_JWKS_URL).json()


def get_user(request: Request):
    """
    Returns:
    {
        is_authenticated: bool,
        user_id: str | None,
        guest_id: str | None,
        email: str | None,
        role: "user" | "guest"
    }
    """
    auth_header = request.headers.get("authorization")
    guest_id = request.headers.get("x-guest-id")

    # Guest
    if not auth_header:
        return {
            "is_authenticated": False,
            "user_id": None,
            "guest_id": guest_id,
            "email": None,
            "role": "guest",
        }

    try:
        token = auth_header.replace("Bearer ", "")

        # get kid from token header
        header = jwt.get_unverified_header(token)
        key = next(k for k in jwks["keys"] if k["kid"] == header["kid"])

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
            issuer=SUPABASE_ISSUER,
        )

        return {
            "is_authenticated": True,
            "user_id": payload.get("sub"),
            "guest_id": guest_id,
            "email": payload.get("email"),
            "role": "user",
        }

    except JWTError as e:
        # token invalid / expired
        print("JWT ERROR:", e)
    except Exception as e:
        print("UNKNOWN AUTH ERROR:", e)

    # fallback to guest
    return {
        "is_authenticated": False,
        "user_id": None,
        "guest_id": guest_id,
        "email": None,
        "role": "guest",
    }
