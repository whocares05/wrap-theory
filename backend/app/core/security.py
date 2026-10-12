import asyncio
import uuid
from dataclasses import dataclass
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from app.core.config import Settings
from app.core.errors import unauthorized


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: uuid.UUID
    email: str


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=300)


def _decode(token: str, settings: Settings) -> AuthenticatedUser:
    try:
        signing_key = _jwks_client(settings.supabase_jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_issuer,
            options={"require": ["exp", "sub", "aud"]},
        )
        subject = uuid.UUID(payload["sub"])
        email = payload.get("email")
        if not isinstance(email, str) or not email:
            raise ValueError("email claim is missing")
        return AuthenticatedUser(user_id=subject, email=email.lower())
    except (jwt.PyJWTError, ValueError, KeyError) as error:
        raise unauthorized("The staff session is invalid or expired") from error


async def verify_supabase_token(token: str, settings: Settings) -> AuthenticatedUser:
    return await asyncio.to_thread(_decode, token, settings)
