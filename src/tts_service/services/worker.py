from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from tts_service.providers.base import SynthesisRequest, TTSProvider
from tts_service.services.jobs import JobService
from tts_service.storage.files import FileStorage


class WorkerService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        file_storage: FileStorage,
        provider: TTSProvider,
        job_service: JobService,
    ) -> None:
        self.session_factory = session_factory
        self.file_storage = file_storage
        self.provider = provider
        self.job_service = job_service

    def process_next_job(self) -> bool:
        with self.session_factory() as session:
            job = self.job_service.claim_next_job(session)
            if job is None:
                return False
            synthesis_input = self.job_service.resolve_synthesis_input(session, job)

            try:
                result = self.provider.synthesize(
                    SynthesisRequest(
                        job_id=job.id,
                        text=job.input_text,
                        voice_profile_id=job.voice_profile_id,
                        request_mode=job.request_mode,
                        reference_audio_path=synthesis_input.reference_audio_path,
                        reference_text=synthesis_input.reference_text,
                    )
                )
                output_path = self.file_storage.save_job_output(job.id, result.audio_bytes, result.format)
                self.job_service.mark_job_succeeded(session, job.id, output_path)
            except Exception as exc:
                self.job_service.mark_job_failed(
                    session,
                    job.id,
                    error_code="synthesis_failed",
                    error_message=str(exc),
                )
            return True
