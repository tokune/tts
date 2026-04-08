from __future__ import annotations

from dataclasses import dataclass

from uuid import uuid4

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from tts_service.db.models import JobEvent, JobInput, TTSJob, VoiceProfile


@dataclass(slots=True)
class CreateJobInput:
    text: str
    job_id: str | None = None
    request_mode: str | None = None
    voice_profile_id: str | None = None
    temp_reference_audio_path: str | None = None
    temp_reference_text: str | None = None


@dataclass(slots=True)
class ResolvedSynthesisInput:
    reference_audio_path: str | None
    reference_text: str | None


class JobService:
    def create_job(self, session: Session, user_id: str, payload: CreateJobInput) -> TTSJob:
        voice = None
        request_mode = "base_tts"
        if payload.voice_profile_id is not None:
            voice = session.scalar(select(VoiceProfile).where(VoiceProfile.id == payload.voice_profile_id))
            if voice is None:
                raise ValueError("voice profile not found")
            if voice.scope != "system" and voice.user_id != user_id:
                raise PermissionError("voice profile is not accessible")
            request_mode = voice.clone_mode
        elif payload.request_mode is not None:
            request_mode = payload.request_mode

        job = TTSJob(
            id=payload.job_id or str(uuid4()),
            user_id=user_id,
            voice_profile_id=voice.id if voice is not None else None,
            status="queued",
            request_mode=request_mode,
            input_text=payload.text,
            output_format="wav",
        )
        session.add(job)
        session.flush()

        if payload.temp_reference_audio_path or payload.temp_reference_text:
            session.add(
                JobInput(
                    job_id=job.id,
                    temp_reference_audio_path=payload.temp_reference_audio_path,
                    temp_reference_text=payload.temp_reference_text,
                )
            )
        session.add(JobEvent(job_id=job.id, status="queued", message="job queued"))
        session.commit()
        session.refresh(job)
        return job

    def get_job_for_user(self, session: Session, user_id: str, job_id: str) -> TTSJob | None:
        return session.scalar(select(TTSJob).where(TTSJob.id == job_id, TTSJob.user_id == user_id))

    def list_jobs_for_user(self, session: Session, user_id: str) -> list[TTSJob]:
        return list(session.scalars(select(TTSJob).where(TTSJob.user_id == user_id).order_by(TTSJob.created_at.desc())))

    def get_job_input(self, session: Session, job_id: str) -> JobInput | None:
        return session.scalar(select(JobInput).where(JobInput.job_id == job_id))

    def resolve_synthesis_input(self, session: Session, job: TTSJob) -> ResolvedSynthesisInput:
        job_input = self.get_job_input(session, job.id)
        if job_input and (job_input.temp_reference_audio_path or job_input.temp_reference_text):
            return ResolvedSynthesisInput(
                reference_audio_path=job_input.temp_reference_audio_path,
                reference_text=job_input.temp_reference_text,
            )

        if job.voice_profile_id is None:
            return ResolvedSynthesisInput(reference_audio_path=None, reference_text=None)

        voice = session.scalar(select(VoiceProfile).where(VoiceProfile.id == job.voice_profile_id))
        if voice is None:
            return ResolvedSynthesisInput(reference_audio_path=None, reference_text=None)

        return ResolvedSynthesisInput(
            reference_audio_path=voice.reference_audio_path,
            reference_text=voice.reference_text,
        )

    def claim_next_job(self, session: Session) -> TTSJob | None:
        job = session.scalar(select(TTSJob).where(TTSJob.status == "queued").order_by(TTSJob.created_at.asc()))
        if job is None:
            return None

        job.status = "running"
        job.started_at = datetime.now(UTC)
        session.add(job)
        session.add(JobEvent(job_id=job.id, status="running", message="job started"))
        session.commit()
        session.refresh(job)
        return job

    def mark_job_succeeded(self, session: Session, job_id: str, output_audio_path: str) -> TTSJob:
        job = session.scalar(select(TTSJob).where(TTSJob.id == job_id))
        if job is None:
            raise ValueError("job not found")

        job.status = "succeeded"
        job.output_audio_path = output_audio_path
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.add(JobEvent(job_id=job.id, status="succeeded", message="job completed"))
        session.commit()
        session.refresh(job)
        return job

    def mark_job_failed(
        self,
        session: Session,
        job_id: str,
        error_code: str,
        error_message: str,
    ) -> TTSJob:
        job = session.scalar(select(TTSJob).where(TTSJob.id == job_id))
        if job is None:
            raise ValueError("job not found")

        job.status = "failed"
        job.error_code = error_code
        job.error_message = error_message
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.add(JobEvent(job_id=job.id, status="failed", message=error_message))
        session.commit()
        session.refresh(job)
        return job

    def cancel_job(self, session: Session, user_id: str, job_id: str) -> TTSJob:
        job = self.get_job_for_user(session, user_id, job_id)
        if job is None:
            raise ValueError("job not found")
        if job.status != "queued":
            raise ValueError("only queued jobs can be cancelled")

        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
        session.add(job)
        session.add(JobEvent(job_id=job.id, status="cancelled", message="job cancelled by user"))
        session.commit()
        session.refresh(job)
        return job
