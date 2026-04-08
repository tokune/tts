from pathlib import Path
from uuid import uuid4


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_voice_reference(self, user_id: str, filename: str, content: bytes) -> str:
        voice_id = str(uuid4())
        suffix = Path(filename).suffix or ".wav"
        path = self.root / "uploads" / "voices" / "users" / user_id / voice_id / f"reference{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def save_system_voice_reference(self, name: str, filename: str, content: bytes) -> str:
        suffix = Path(filename).suffix or ".wav"
        path = self.root / "uploads" / "voices" / "system" / name / f"reference{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def save_job_output(self, job_id: str, content: bytes, extension: str = "wav") -> str:
        path = self.root / "outputs" / "jobs" / job_id / f"audio.{extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)

    def save_job_reference(self, job_id: str, filename: str, content: bytes) -> str:
        suffix = Path(filename).suffix or ".wav"
        path = self.root / "uploads" / "jobs" / job_id / f"input_reference{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)
