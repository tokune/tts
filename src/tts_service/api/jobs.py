from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tts_service.auth.deps import AuthenticatedUser, get_db_session, require_api_key
from tts_service.services.jobs import CreateJobInput, JobService
from tts_service.storage.files import FileStorage

router = APIRouter()


class CreateJobRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_profile_id: str | None = None


class JobResponse(BaseModel):
    id: str
    status: str
    request_mode: str
    voice_profile_id: str | None
    output_audio_path: str | None
    error_code: str | None
    error_message: str | None
    audio_url: str | None = None


def get_job_service(request: Request) -> JobService:
    return request.app.state.job_service


def get_file_storage(request: Request) -> FileStorage:
    return request.app.state.file_storage


@router.post("/v1/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
async def create_job(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    job_service: JobService = Depends(get_job_service),
    file_storage: FileStorage = Depends(get_file_storage),
) -> JobResponse:
    content_type = request.headers.get("content-type", "")
    payload = await parse_job_request(request, content_type, file_storage)
    try:
        job = job_service.create_job(
            session=session,
            user_id=current_user.user_id,
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return build_job_response(job)


@router.get("/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    current_user: AuthenticatedUser = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    job = job_service.get_job_for_user(session, current_user.user_id, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return build_job_response(job)


@router.get("/v1/jobs", response_model=list[JobResponse])
def list_jobs(
    current_user: AuthenticatedUser = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    job_service: JobService = Depends(get_job_service),
) -> list[JobResponse]:
    jobs = job_service.list_jobs_for_user(session, current_user.user_id)
    return [build_job_response(job) for job in jobs]


@router.post("/v1/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(
    job_id: str,
    current_user: AuthenticatedUser = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    job_service: JobService = Depends(get_job_service),
) -> JobResponse:
    try:
        job = job_service.cancel_job(session, current_user.user_id, job_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail == "job not found" else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return build_job_response(job)


@router.get("/v1/jobs/{job_id}/audio")
def download_job_audio(
    job_id: str,
    current_user: AuthenticatedUser = Depends(require_api_key),
    session: Session = Depends(get_db_session),
    job_service: JobService = Depends(get_job_service),
) -> FileResponse:
    job = job_service.get_job_for_user(session, current_user.user_id, job_id)
    if job is None or not job.output_audio_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audio not found")
    return FileResponse(path=job.output_audio_path, media_type="audio/wav", filename=f"{job.id}.wav")


def build_job_response(job) -> JobResponse:
    audio_url = f"/v1/jobs/{job.id}/audio" if job.output_audio_path else None
    return JobResponse.model_validate(
        {
            "id": job.id,
            "status": job.status,
            "request_mode": job.request_mode,
            "voice_profile_id": job.voice_profile_id,
            "output_audio_path": job.output_audio_path,
            "error_code": job.error_code,
            "error_message": job.error_message,
            "audio_url": audio_url,
        }
    )


async def parse_job_request(request: Request, content_type: str, file_storage: FileStorage) -> CreateJobInput:
    if content_type.startswith("application/json"):
        payload = CreateJobRequest.model_validate(await request.json())
        return CreateJobInput(text=payload.text, voice_profile_id=payload.voice_profile_id)

    if content_type.startswith("multipart/form-data") or content_type.startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        text = str(form.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="text is required")

        voice_profile_id = form.get("voice_profile_id")
        if voice_profile_id is not None:
            return CreateJobInput(text=text, voice_profile_id=str(voice_profile_id))

        reference_audio = form.get("reference_audio")
        if reference_audio is None:
            return CreateJobInput(text=text)

        clone_mode = str(form.get("clone_mode", "clone"))
        reference_text = form.get("reference_text")
        if clone_mode == "ultimate_clone" and not reference_text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reference_text is required")

        job_id = str(uuid4())
        content = await reference_audio.read()
        temp_path = file_storage.save_job_reference(job_id, reference_audio.filename or "reference.wav", content)
        return CreateJobInput(
            job_id=job_id,
            text=text,
            request_mode=clone_mode,
            temp_reference_audio_path=temp_path,
            temp_reference_text=str(reference_text) if reference_text else None,
        )

    raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported content type")
