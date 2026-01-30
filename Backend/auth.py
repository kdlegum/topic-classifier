import requests
from jose import jwt
from fastapi import Request

SUPABASE_PROJECT_ID = "aefhkwhqvlcbvdpoyokn"
SUPABASE_JWKS_URL = (
    f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1/.well-known/jwks.json"
)

jwks = requests.get(SUPABASE_JWKS_URL).json()


def get_user(request: Request):
    """
    Input: HTTP Request
    Output: {
    is_authenticated: bool,
    user_id: str | None,
    guest_id: str | None,
    email: str | None,
    role: "user" | "guest"
    } 
    """
    auth_header = request.headers.get("authorization")
    guest_id = request.headers.get("x-guest-id")

    # ----- Guest (no auth header) -----
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

        header = jwt.get_unverified_header(token)

        key = next(
            k for k in jwks["keys"]
            if k["kid"] == header["kid"]
        )

        # Verify token
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience="authenticated",
        )

        return {
            "is_authenticated": True,
            "user_id": payload["sub"],
            "guest_id": None,
            "email": payload.get("email"),
            "role": "user",
        }

    except Exception:
        return {
            "is_authenticated": False,
            "user_id": None,
            "guest_id": guest_id,
            "email": None,
            "role": "guest",
        }
