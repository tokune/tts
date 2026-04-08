from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from tts_service.db.models import VoiceProfile
from tts_service.storage.files import FileStorage


@dataclass(slots=True)
class CreateVoiceProfileInput:
    user_id: str
    name: str
    clone_mode: str
    consent_statement: str
    reference_audio_filename: str
    reference_audio_content: bytes
    reference_text: str | None = None
    description: str | None = None
    source_label: str | None = None


class VoiceService:
    def __init__(self, file_storage: FileStorage) -> None:
        self.file_storage = file_storage

    def create_voice_profile(self, session: Session, payload: CreateVoiceProfileInput) -> VoiceProfile:
        stored_path = self.file_storage.save_voice_reference(
            user_id=payload.user_id,
            filename=payload.reference_audio_filename,
            content=payload.reference_audio_content,
        )
        voice = VoiceProfile(
            user_id=payload.user_id,
            scope="user",
            name=payload.name,
            description=payload.description,
            clone_mode=payload.clone_mode,
            reference_audio_path=stored_path,
            reference_text=payload.reference_text,
            sample_rate=None,
            duration_ms=None,
            consent_statement=payload.consent_statement,
            source_label=payload.source_label,
            status="ready",
        )
        session.add(voice)
        session.commit()
        session.refresh(voice)
        return voice

    def list_voices_for_user(self, session: Session, user_id: str) -> list[VoiceProfile]:
        return list(
            session.scalars(
                select(VoiceProfile)
                .where((VoiceProfile.user_id == user_id) | (VoiceProfile.scope == "system"))
                .order_by(VoiceProfile.created_at.desc())
            )
        )

    def create_system_voice(
        self,
        session: Session,
        name: str,
        clone_mode: str,
        reference_audio_filename: str,
        reference_audio_content: bytes,
        reference_text: str | None = None,
        description: str | None = None,
        source_label: str | None = None,
    ) -> VoiceProfile:
        stored_path = self.file_storage.save_system_voice_reference(
            name=name,
            filename=reference_audio_filename,
            content=reference_audio_content,
        )
        voice = VoiceProfile(
            user_id=None,
            scope="system",
            name=name,
            description=description,
            clone_mode=clone_mode,
            reference_audio_path=stored_path,
            reference_text=reference_text,
            sample_rate=None,
            duration_ms=None,
            consent_statement="system voice",
            source_label=source_label or name,
            status="ready",
        )
        session.add(voice)
        session.commit()
        session.refresh(voice)
        return voice

    def load_system_voices_from_manifest(self, session: Session, manifest_path: Path) -> None:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in entries:
            source_label = str(entry.get("source_label") or entry["name"])
            existing = session.scalar(
                select(VoiceProfile).where(
                    VoiceProfile.scope == "system",
                    VoiceProfile.source_label == source_label,
                )
            )
            if existing is not None:
                continue

            reference_path = Path(entry["audio_path"])
            self.create_system_voice(
                session=session,
                name=str(entry["name"]),
                clone_mode=str(entry.get("clone_mode", "clone")),
                reference_audio_filename=reference_path.name,
                reference_audio_content=reference_path.read_bytes(),
                reference_text=str(entry["reference_text"]) if entry.get("reference_text") else None,
                description=str(entry["description"]) if entry.get("description") else None,
                source_label=source_label,
            )
