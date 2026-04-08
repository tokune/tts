from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tts_service.auth.deps import AuthenticatedUser, get_db_session, require_api_key
from tts_service.services.voices import CreateVoiceProfileInput, VoiceService

router = APIRouter()


class VoiceProfileResponse(BaseModel):
    id: str
    name: str
    scope: str
    clone_mode: str
    reference_text: str | None
    status: str


class VoiceProfileListResponse(BaseModel):
    items: list[VoiceProfileResponse]


def get_voice_service(request: Request) -> VoiceService:
    return request.app.state.voice_service


@router.post("/v1/voices", status_code=status.HTTP_201_CREATED, response_model=VoiceProfileResponse)
async def create_voice_profile(
    name: Annotated[str, Form()],
    clone_mode: Annotated[str, Form()],
    consent_statement: Annotated[str, Form()],
    reference_audio: UploadFile = File(...),
    reference_text: Annotated[str | None, Form()] = None,
    current_user: AuthenticatedUser = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    voice_service: VoiceService = Depends(get_voice_service),
) -> VoiceProfileResponse:
    if clone_mode not in {"clone", "ultimate_clone"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unsupported clone mode")
    if clone_mode == "ultimate_clone" and not reference_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reference_text is required")

    content = await reference_audio.read()
    voice = voice_service.create_voice_profile(
        session,
        CreateVoiceProfileInput(
            user_id=current_user.user_id,
            name=name,
            clone_mode=clone_mode,
            consent_statement=consent_statement,
            reference_audio_filename=reference_audio.filename or "reference.wav",
            reference_audio_content=content,
            reference_text=reference_text,
        ),
    )
    return VoiceProfileResponse.model_validate(voice, from_attributes=True)


@router.get("/v1/voices", response_model=VoiceProfileListResponse)
def list_voice_profiles(
    current_user: AuthenticatedUser = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    voice_service: VoiceService = Depends(get_voice_service),
) -> VoiceProfileListResponse:
    voices = voice_service.list_voices_for_user(session, current_user.user_id)
    return VoiceProfileListResponse(
        items=[VoiceProfileResponse.model_validate(voice, from_attributes=True) for voice in voices]
    )
