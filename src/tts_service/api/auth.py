from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from tts_service.auth.deps import AuthenticatedUser, get_db_session, require_api_key
from tts_service.auth.security import generate_api_key, hash_api_key
from tts_service.db.models import User

router = APIRouter()


class BootstrapUserRequest(BaseModel):
    name: str


class BootstrapUserResponse(BaseModel):
    user_id: str
    name: str
    api_key: str


class VerifyApiKeyResponse(BaseModel):
    valid: bool
    user_id: str
    name: str


@router.post("/debug/bootstrap-user", status_code=status.HTTP_201_CREATED, response_model=BootstrapUserResponse)
def bootstrap_user(payload: BootstrapUserRequest, session: Session = Depends(get_db_session)) -> BootstrapUserResponse:
    raw_api_key = generate_api_key()
    user = User(name=payload.name, api_key_hash=hash_api_key(raw_api_key))
    session.add(user)
    session.commit()
    session.refresh(user)
    return BootstrapUserResponse(user_id=user.id, name=user.name, api_key=raw_api_key)


@router.post("/v1/auth/keys/verify", response_model=VerifyApiKeyResponse)
def verify_api_key(current_user: AuthenticatedUser = Depends(require_api_key)) -> VerifyApiKeyResponse:
    return VerifyApiKeyResponse(valid=True, user_id=current_user.user_id, name=current_user.name)
