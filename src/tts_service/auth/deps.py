from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from tts_service.auth.security import hash_api_key
from tts_service.db.models import User


@dataclass(slots=True)
class AuthenticatedUser:
    user_id: str
    name: str


def get_db_session(request: Request) -> Session:
    return request.state.db_session


def require_api_key(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")

    api_key = authorization.removeprefix("Bearer ").strip()
    user = session.scalar(select(User).where(User.api_key_hash == hash_api_key(api_key), User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")

    return AuthenticatedUser(user_id=user.id, name=user.name)
