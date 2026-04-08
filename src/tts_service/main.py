from typing import Any

from fastapi import FastAPI, Request

from tts_service.api.auth import router as auth_router
from tts_service.api.jobs import router as jobs_router
from tts_service.api.voices import router as voices_router
from tts_service.config import Settings, build_settings
from tts_service.db.session import create_session_factory
from tts_service.providers.fake import FakeTTSProvider
from tts_service.providers.base import TTSProvider
from tts_service.providers.nanovllm_voxcpm import NanoVllmVoxCpmProvider
from tts_service.providers.official_voxcpm import OfficialVoxCPMProvider
from tts_service.services.jobs import JobService
from tts_service.services.voices import VoiceService
from tts_service.storage.files import FileStorage


def build_provider(settings: Settings) -> TTSProvider:
    if settings.provider == "fake":
        return FakeTTSProvider()
    if settings.provider == "nanovllm_voxcpm":
        return NanoVllmVoxCpmProvider(
            model_path=settings.voxcpm_model_path,
            device_ids=settings.voxcpm_device_ids,
        )
    if settings.provider == "voxcpm":
        return OfficialVoxCPMProvider(
            model_path=settings.voxcpm_model_path,
            device_ids=settings.voxcpm_device_ids,
        )
    raise ValueError(f"unsupported provider: {settings.provider}")


def create_app(overrides: dict[str, Any] | None = None) -> FastAPI:
    settings = build_settings(overrides)
    session_factory = create_session_factory(settings.database_url)

    app = FastAPI(title=settings.app_name)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.file_storage = FileStorage(settings.storage_root)
    app.state.voice_service = VoiceService(app.state.file_storage)
    app.state.job_service = JobService()
    app.state.provider = build_provider(settings)

    with session_factory() as session:
        if settings.system_voices_manifest_path is not None:
            app.state.voice_service.load_system_voices_from_manifest(
                session=session,
                manifest_path=settings.system_voices_manifest_path,
            )

    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next):
        session = session_factory()
        request.state.db_session = session
        try:
            response = await call_next(request)
            session.commit()
            return response
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    app.include_router(jobs_router)
    app.include_router(voices_router)

    return app
