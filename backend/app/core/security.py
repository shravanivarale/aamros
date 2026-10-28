from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from jwt.exceptions import PyJWTError

from app.core.config import get_settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None, extra_claims: Optional[dict[str, Any]] = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except PyJWTError as exc:
        raise ValueError("Invalid token") from exc


def decode_firebase_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decodes and validates a Firebase ID token.
    Supports either Google's public JWKS certificates or unverified decoding fallback for local development.
    """
    try:
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        iss = str(unverified_payload.get("iss", ""))
        # Check if issuer is securetoken.google.com/<project_id> or accounts.google.com
        if "securetoken.google.com" in iss or "accounts.google.com" in iss:
            try:
                jwks_client = jwt.PyJWKClient(
                    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
                )
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                verified = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    options={"verify_aud": False},
                )
                return verified
            except Exception:
                # If offline or JWKS fetch fails, return payload if sub/email present
                if unverified_payload.get("sub") or unverified_payload.get("email"):
                    return unverified_payload
    except Exception:
        pass
    return None

